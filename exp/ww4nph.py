from periscope import Network
from periscope.layers import LandmarkLayer
import lasagne
from lasagne.layers import Conv2DLayer, MaxPool2DLayer, DropoutLayer
from lasagne.layers.normalization import batch_norm
from lasagne.init import HeUniform
from lasagne.nonlinearities import identity
import numpy as np

class Ww4nph(Network):

    def init_constants(self):
        super(Ww4nph, self).init_constants()
        self.crop_size = (108, 108)
        self.batch_size = 64
        self.learning_rates = np.concatenate((
            [0.005] * 10,
            [0.0005] * 10,
            [0.00005] * 10,
            [0.000005] * 10
        ))

    def hidden_layers(self, network, **kwargs):
        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 1st. Data size 108->106
        network = Conv2DLayer(network, 64, (3, 3), pad=0,
            W=HeUniform('relu'))
        network = batch_norm(network, gamma=None)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 2nd. Data size 106->104
        network = Conv2DLayer(network, 64, (3, 3), pad=0,
            W=HeUniform('relu'))
        network = batch_norm(network, gamma=None)

        # Max pool. Data size 104->52
        network = MaxPool2DLayer(network, (2, 2), stride=2)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 3rd. Data size 52->50
        network = Conv2DLayer(network, 128, (3, 3), pad=0,
            W=HeUniform('relu'))
        network = batch_norm(network, gamma=None)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 4th. Data size 50->48
        network = Conv2DLayer(network, 128, (3, 3), pad=0,
            W=HeUniform('relu'))
        network = batch_norm(network, gamma=None)

        # Max pool. Data size 48->24
        network = MaxPool2DLayer(network, (2, 2), stride=2)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 5th. Data size 24->22
        network = Conv2DLayer(network, 256, (3, 3), pad=0,
            W=HeUniform('relu'), name='conv5')
        network = batch_norm(network, gamma=None)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 6th. Data size 22->20
        network = Conv2DLayer(network, 256, (3, 3), pad=0,
            W=HeUniform('relu'), name='conv6')
        network = batch_norm(network, gamma=None)

        # Max pool.  Data size 20->10
        network = MaxPool2DLayer(network, (2, 2), stride=2)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 7th. Data size 10->8
        network = Conv2DLayer(network, 512, (3, 3), pad=0,
            W=HeUniform('relu'), name='conv7')
        network = batch_norm(network, gamma=None)

        # EXPERIMENT
        # Add landmarks!
        network = LandmarkLayer(network, kinds='vhc')

        # 8th. Data size 8->6
        network = Conv2DLayer(network, 512, (3, 3), pad=0,
            W=HeUniform('relu'), name='conv8')
        network = batch_norm(network, gamma=None)

        # Max pool.  Data size 6->3
        network = MaxPool2DLayer(network, (2, 2), stride=2)

        # 9th. Data size 3->1
        network = Conv2DLayer(network, 1024, (3, 3), pad=0,
            W=HeUniform('relu'), name='fc9')
        # network = lasagne.layers.DenseLayer(network, 1024, W=HeUniform('relu'))
        network = batch_norm(network, gamma=None)

        network = DropoutLayer(network)

        return network

    def regularize_parameters(self):
        l2 = lasagne.regularization.regularize_network_params(
            self.network, lasagne.regularization.l2) * 5e-3
        return l2