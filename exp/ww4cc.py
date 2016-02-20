from periscope import Network
from periscope.layers import QuickNormLayer, QuickMeanLayer
import lasagne
from lasagne.layers import Conv2DLayer, MaxPool2DLayer, DropoutLayer
from lasagne.layers import NonlinearityLayer
from lasagne.layers.normalization import batch_norm
from lasagne.init import HeUniform
from lasagne.nonlinearities import identity
import numpy as np

def double_norm(layer):
    """
    Applies batchnorm twice, once before the nonlinearity, and again after!
    """
    nonlinearity = getattr(layer, 'nonlinearity', None)
    if nonlinearity is not None:
        layer.nonlinearity = lasagne.nonlinearities.identity
    if hasattr(layer, 'b'):
        del layer.params[layer.b]
        layer.b = None
    network = QuickMeanLayer(layer)
    network = NonlinearityLayer(network, nonlinearity)
    return QuickNormLayer(layer)

def quick_mean(layer):
    """
    Convenience function to apply batch normalization to a given layer's output.
    Will steal the layer's nonlinearity if there is one (effectively introducing
    the normalization right before the nonlinearity), and will remove the
    layer's bias if there is one (because it would be redundant).
    @param layer: The `Layer` instance to apply the normalization to; note that
        it will be irreversibly modified as specified above
    @return: A `BatchNormLayer` instance stacked on the given `layer`
    """
    nonlinearity = getattr(layer, 'nonlinearity', None)
    if nonlinearity is not None:
        layer.nonlinearity = lasagne.nonlinearities.identity
    if hasattr(layer, 'b'):
        del layer.params[layer.b]
        layer.b = None
    network = QuickMeanLayer(layer)
    return NonlinearityLayer(network, nonlinearity)

class Ww4cc(Network):
    """
    The idea: add QuickNorm after max pooling to recenter responses.
    """

    def init_constants(self):
        super(Ww4cc, self).init_constants()
        self.crop_size = (96, 96)
        self.batch_size = 64
        self.learning_rates = np.concatenate((
            [0.005] * 10,
            [0.0005] * 10,
            [0.00005] * 10,
            [0.000005] * 10
        ))

    def hidden_layers(self, network, **kwargs):
        # 1st. Data size 96->96
        network = Conv2DLayer(network, 64, (3, 3), pad='same',
            W=HeUniform('relu'))
        network = double_norm(network)
        # 2nd. Data size 96->96
        network = Conv2DLayer(network, 64, (3, 3), pad='same',
            W=HeUniform('relu'))
        network = quick_mean(network)

        # Max pool. Data size 96->48
        network = MaxPool2DLayer(network, (2, 2), stride=2)
        network = double_norm(network)

        # 3rd. Data size 48->48
        network = Conv2DLayer(network, 128, (3, 3), pad='same',
            W=HeUniform('relu'))
        network = double_norm(network)
        # 4th. Data size 48->48
        network = Conv2DLayer(network, 128, (3, 3), pad='same',
            W=HeUniform('relu'))
        network = quick_mean(network)

        # Max pool. Data size 48->24
        network = MaxPool2DLayer(network, (2, 2), stride=2)
        network = double_norm(network)

        # 5th. Data size 24->24
        network = Conv2DLayer(network, 256, (3, 3), pad='same',
            W=HeUniform('relu'), name='conv5')
        network = double_norm(network)
        # 6th. Data size 24->24
        network = Conv2DLayer(network, 256, (3, 3), pad='same',
            W=HeUniform('relu'), name='conv6')
        network = quick_mean(network)

        # Max pool.  Data size 24->12
        network = MaxPool2DLayer(network, (2, 2), stride=2)
        network = double_norm(network)

        # 7th. Data size 12->12
        network = Conv2DLayer(network, 512, (3, 3), pad='same',
            W=HeUniform('relu'), name='conv7')
        network = double_norm(network)
        # 8th. Data size 12->12
        network = Conv2DLayer(network, 512, (3, 3), pad='same',
            W=HeUniform('relu'), name='conv8')
        network = quick_mean(network)

        # Max pool.  Data size 12->6
        network = MaxPool2DLayer(network, (2, 2), stride=2)
        network = double_norm(network)

        # 9th. Data size 6->1
        network = lasagne.layers.DenseLayer(network, 1024, W=HeUniform('relu'))

        network = DropoutLayer(network)

        return network

    def regularize_parameters(self):
        l2 = lasagne.regularization.regularize_network_params(
            self.network, lasagne.regularization.l2) * 5e-3
        return l2