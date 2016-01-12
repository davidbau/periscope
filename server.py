#!/usr/bin/env python3

import os
import posixpath
import itertools
import urllib.parse
import numpy
import scipy.ndimage
import base64
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, HTTPServer
from templet import templet
from model import Model
from PIL import Image

class TextMap:
  def __init__(self, filename, trim=0):
    self._data = {}
    self._inv = {}
    self._keys = []
    for line in open(filename, 'r').readlines():
      key, val = line.split()
      key = key[trim:]
      val = int(val)
      self._data[key] = val
      self._inv[val] = key
      self._keys.append(key)
  def name(self, val):
    return self._inv[val]
  def num(self, key):
    return self._data[key]
  def names(self):
    return self._keys

class MiniPlacesData:
  def __init__(self, devkit):
    self._categories = TextMap(os.path.join(devkit, 'categories.txt'), trim=3)
    self._train = TextMap(os.path.join(devkit, 'train.txt'))
    self._val = TextMap(os.path.join(devkit, 'val.txt'))
  def label(self, filename):
    if filename.startswith('val'):
      cat = self._val.num(filename)
    else:
      cat = self._train.num(filename)
    return cat
  def catname(self, cat):
    return self._categories.name(cat)

miniplaces = MiniPlacesData('mp-dev_kit')
models = {
  'see1': Model('see', 'exp-see-1/epoch-024.mdl'),
  'see2': Model('see', 'exp-see-2/epoch-028.mdl'),
  'uni': Model('uni', 'exp-uni-1/epoch-027.mdl'),
  'unq': Model('unq', 'exp-unq/epoch-029.mdl'),
  'ren': Model('ren', 'exp-ren/epoch-029.mdl'),
}

# force a compile on startup
# debug_fn = models[0].debug_fn()

class Classification:
  def __init__(self, model, imgpath):
    self.model = model
    path = os.path.join('mp-data/images', imgpath)
    self.image = numpy.transpose(
            scipy.ndimage.imread(path), [2, 0, 1]) / 255.0
    results = model.debug_fn()(numpy.expand_dims(self.image, axis=0))
    self.results = []
    for i, layer in enumerate(model.named_layers()):
        self.results.append((layer, results[i]))

class ClassificationCache:
  def __init__(self):
    self._cache = {}

  def lookup(self, modelname, imgpath):
    if imgpath not in self._cache:
      self._cache[(modelname, imgpath)] = Classification(
          models[modelname], imgpath)  
    return self._cache[(modelname, imgpath)]

grid_slices = [
    (slice(y, y+23), slice(x, x+23))
    for x in range(0, 112, 7) for y in range(0, 112, 7)]

# A clipping rectifier, pegging values less than t1 to 0 and more than t2 to 1.
def peg(ar, t1, t2):
    return numpy.clip((ar - t1) / (t2 - t1), 0, 1)

def response_image(img, vec):
    epsilon = 1e-6
    avg = numpy.mean(vec)
    std = numpy.std(vec)
    respmax = avg + std
    resp = numpy.clip((respmax - vec) / (2 * std + epsilon), 0, 1)
    total = numpy.zeros(img.shape)
    count = numpy.zeros(img.shape)
    for i, s in enumerate(grid_slices):
        total[(slice(None), s[0], s[1])] += resp[i]
        count[(slice(None), s[0], s[1])] += 1
    mask = total / count
    mask = peg((mask - mask.mean()) / (mask.std() + epsilon), -0.2, 0.2)
    masked = img * mask
    im3 = scipy.misc.bytescale(
        numpy.transpose(masked, [1, 2, 0]), cmin=0, cmax=1)
    return rgbi_image(im3)

def rgbi_image(im3, title=None):
    if title is None:
        attr = ''
    else:
        attr = ' title="{}"'.format(title)
    height = im3.shape[1]
    while height < 64:
        height *= 2
    png_buffer = BytesIO()
    im = Image.frombytes('RGB', (im3.shape[1], im3.shape[0]), im3.tostring())
    im.save(png_buffer, format="PNG")
    b64 = base64.b64encode(png_buffer.getvalue()).decode('ascii')
    return '<img height={} src="data:img/png;base64,{}"{}>'.format(
        height, b64, attr)


class ResponseProbe:
  def __init__(self, model, imgpath):
    self.model = model
    path = os.path.join('mp-data/images', imgpath)
    self.image = numpy.transpose(
            scipy.ndimage.imread(path), [2, 0, 1]) / 255.0
    self.probe = numpy.repeat(numpy.expand_dims(self.image, axis=0),
            len(grid_slices), axis=0)
    gray = numpy.ones((3, 23, 23)) * 0.5
    for i, (sy, sx) in enumerate(grid_slices):
        self.probe[(i, slice(0, 3), sy, sx)] = gray
    results = model.debug_fn()(self.probe)
    self.results = []
    for i, layer in enumerate(model.named_layers()):
        self.results.append((layer, results[i]))

  def get_response_image(self, name, channel, y=0, x=0):
    result = [r for (layer, r) in self.results if layer.name == name][0]
    if len(result.shape) == 4:
      vec = result[:,channel,y,x]
    else:
      vec = result[:,channel]
    return response_image(self.image, vec)

class ResponseProbeCache:
  def __init__(self):
    self._cache = {}

  def lookup(self, modelname, imgpath):
    if imgpath not in self._cache:
      self._cache[(modelname, imgpath)] = ResponseProbe(
          models[modelname], imgpath)  
    return self._cache[(modelname, imgpath)]

def extract_resp_region(resp):
    avg = numpy.average(resp)
    std = numpy.std(resp)
    respmax = avg + std
    respmin = avg - std
    resp = numpy.minimum(
            numpy.maximum((respmax - resp) /
            (respmax - respmin + 1e-6), 0), 1)
    smeared = numpy.zeros([128, 128])
    smearedd = numpy.ones([128, 128]) * 0.01
    # Some geometric parameters
    res = 16
    pix = 23
    st = 7
    for x in range(res):
        for y in range(res):
            smeared[y*st:y*st+pix, x*st:x*st+pix] += resp[y][x]
            smearedd[y*st:y*st+pix, x*st:x*st+pix] += 1
    return peg(numpy.clip(gaussian_filter(
            numpy.divide(smeared, smearedd), sigma=st), 0, 1), 0.4, 0.6)

classification_cache = ClassificationCache()
response_cache = ResponseProbeCache()

# HTTPRequestHandler class
class PeriscopeRequestHandler(SimpleHTTPRequestHandler):
  def do_GET(self):
    if self.path.startswith('/info/'):
      return self.do_info()
    super().do_GET()

  def do_info(self):
    [_, _, modelname, imgpath] = self.path.split('/', 3)
    label = miniplaces.label(imgpath)
    cat = miniplaces.catname(label)
    cl = classification_cache.lookup(modelname, imgpath)
    rp = response_cache.lookup(modelname, imgpath)

    self.results = cl.results
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.end_headers()    
    self.wfile.write(self.info_template(
        imgpath, label, cat, cl, rp).encode('utf-8'))

  def result_for_layer(self, name):
    return [result for layer, result in self.results if layer.name == name][0]

  @templet
  def info_template(self, imgpath, label, cat, cl, rp):
    """\
    <html>
    <style>
    img { image-rendering: pixelated; margin:1px; }
    </style>
    <body>
    <img src="/img/$imgpath">
    <p>Category: $cat
    <p>Layers
    ${[self.layer_template(layer, result, rp) for layer, result in cl.results]}
    </body>
    </html>
    """

  @templet
  def layer_template(self, layer, result, rp):
    """\
    <p>${layer.name}
    <p>Shape: ${result.shape}
    ${self.layer_details(layer, result, rp)}
    """

  def layer_details(self, layer, result, rp):
    if layer.name == 'softmax':
      return self.softmax_details(layer, result, rp)
    elif layer.name == 'input':
      return self.input_details(layer, result)
    elif len(result.shape) == 4 and result.shape[2] > 1:
      if hasattr(layer, 'prelu') and hasattr(layer, 'bn'):
        return self.conv_details(layer, result)
      return '<p>' + self.conv_images(layer, result)
    else:
      if hasattr(layer, 'prelu') and hasattr(layer, 'bn'):
        return self.fc_details(layer, result)
    return '<p>' + layer.name

  @templet
  def softmax_details(self, layer, result, rp):
    """\
    <p>W shape ${layer.W.get_value().shape},
    <p>
    ${{
      input_layer = layer.input_layer
      goo8c = self.result_for_layer('goo8c')[0,:,0,0]
      weights = layer.W.get_value()
      biases = layer.b.get_value()
      sorted = []
      for i in range(result.shape[1]):
        cat = miniplaces.catname(i)
        comps = numpy.multiply(weights[:,i], goo8c)
        pieces = []
        for j in range(comps.shape[0]):
          pieces.append((comps[j], j))
        pieces.sort()
        pieces.reverse()
        pieces = pieces[:20]
        numbers = '; '.join(['c{}: {}'.format(j, c) for c, j in pieces])
        component_ri = ''.join([rp.get_response_image('goo8c', j) for c, j in pieces])
        ri = rp.get_response_image('softmax', i)
        sorted.append(
            (result[0, i], cat, numbers, ri, component_ri))
      sorted.sort()
      sorted = sorted[-5:]
      out.extend(['{}: {} {}<br>{}{}<br>'.format(cat, r, n, im, ri) for (r, cat, n, im, ri) in sorted])
    }}
    """

  def input_details(self, layer, result):
    out = ['<p>']
    for i in range(result.shape[1]):
      data = result[0, i]
      out.append(self.image_for_array(data, cmin=0, cmax=1,
          title="{}_{}".format(layer.name, i)))
    return ''.join(out)

  @templet
  def conv_details(self, layer, result):
    """\
    <p>Prelu alpha mean: ${numpy.mean(layer.prelu.alpha.get_value())}<br>
    BN mean: ${numpy.mean(layer.bn.mean.get_value())},
    BN inv_std ${numpy.mean(layer.bn.inv_std.get_value())}<br>
    ${self.conv_images(layer, result)}
    """

  @templet
  def conv_images(self, layer, result):
    """\
    ${{
      result = numpy.array(result)
      out.append('First image shape {}<br>'.format(result[0, 0].shape))
      out.append('First pixel {}<br>'.format(result[0, 0, 0, 0]))
      if hasattr(layer, 'bn'):
        out.append('First pix bnm{} bnis{} normed{}<br>'.format(
            layer.bn.mean.get_value()[0],
            layer.bn.inv_std.get_value()[0],
            (result[0, 0, 0, 0] -
            layer.bn.mean.get_value()[0]) *
            layer.bn.inv_std.get_value()[0]))
      for i in range(result.shape[1]):
        data = result[0, i]
        if hasattr(layer, 'bn'):
          data = data - layer.bn.mean.get_value()[i]
          data = data * layer.bn.inv_std.get_value()[i]
        out.append(self.image_for_array(data,
               title="{}_{}".format(layer.name, i)))
    }}
    """

  @templet
  def fc_details(self, layer, result):
    """\
    <p>${numpy.array_str(layer.W.get_value())}<br>
    ${numpy.array_str(layer.prelu.alpha.get_value())}
    <p>Prelu alpha mean: ${numpy.mean(layer.prelu.alpha.get_value())}<br>
    BN mean: ${numpy.mean(layer.bn.mean.get_value())},
    BN inv_std ${numpy.mean(layer.bn.inv_std.get_value())}<br>
    ${{
      sorted = []
      result = numpy.array(result)
      for i in range(result.shape[1]):
        data = result[0, i, 0, 0]
        sorted.append((data, '{}_{}'.format(layer.name, i)))
      sorted.sort()
      out.extend(['{}: {}<br>'.format(cat, r) for (r, cat) in sorted])
    }}
    """

  def image_for_array(self, arr, cmin=0, cmax=2, cneg=-4, title=""):
    imb = scipy.misc.bytescale(arr, cmin=cmin, cmax=cmax)
    imo = scipy.misc.bytescale(arr, cmin=cmax, cmax=cmax*2)
    imn = scipy.misc.bytescale(-arr, cmin=-cmin, cmax=-cneg)
    im3 = numpy.repeat(numpy.expand_dims(imb, axis=2), 3, axis=2)
    im3[:,:,2] += imn
    im3[:,:,2] -= imo
    return rgbi_image(im3)

  def translate_path_into_dir(self, subdir, trim, path):
    path = posixpath.normpath(urllib.parse.unquote(path))
    words = path.split('/')
    words = filter(None, words)
    words = itertools.islice(words, trim, None)
    path = subdir
    for word in words:
      drive, word = os.path.splitdrive(word)
      head, word = os.path.split(word)
      if word in (os.curdir, os.pardir): continue
      path = os.path.join(path, word)
    print(path)
    return path 
 
  # Directories to serve
  def translate_path(self, path):
    if path.startswith('/img/'):
      return self.translate_path_into_dir('mp-data/images', 1, path)
    return ''
 
def run():
  print('starting server...')
 
  # Server settings
  # Choose port 8080, for port 80, which is normally used for a http server, you need root access
  server_address = ('127.0.0.1', 8081)
  httpd = HTTPServer(server_address, PeriscopeRequestHandler)
  print('running server...')
  httpd.serve_forever()
 
 
run()
