import os
import numpy as np
seed = 123
rng = np.random.RandomState(seed)
from mlp.data_providers import MSD10GenreDataProvider, MSD25GenreDataProvider

class AugmentedMSD10DataProvider(MSD10GenreDataProvider):
    """Data provider for MNIST dataset which transforms images using a variety of possible autoencoders (potentially) trained with added noise"""

    def __init__(self, which_set='train', batch_size=50, max_num_batches=-1,
                 shuffle_order=True, rng=rng,fraction=0.25,std=0.05,pdrop=0.2):
        """Create a new augmented MNIST data provider object.

        Args:
            which_set: One of 'train', 'valid' or 'test'. Determines which
                portion of the MNIST data this object should provide.
            batch_size (int): Number of data points to include in each batch.
            max_num_batches (int): Maximum number of batches to iterate over
                in an epoch. If `max_num_batches * batch_size > num_data` then
                only as many batches as the data can be split into will be
                used. If set to -1 all of the data will be used.
            shuffle_order (bool): Whether to randomly permute the order of
                the data before each epoch.
            rng (RandomState): A seeded random number generator.
            transformer: Function which takes an `inputs` array of shape
                (batch_size, input_dim) corresponding to a batch of input
                images and a `rng` random number generator object (i.e. a
                call signature `transformer(inputs, rng)`) and applies a
                potentiall random set of transformations to some / all of the
                input images as each new batch is returned when iterating over
                the data provider.
        """
        super(AugmentedMSD10DataProvider,self).__init__(
            which_set, batch_size, max_num_batches, shuffle_order, rng)
        self.fraction = fraction
        self.std = std
        self.pdrop = pdrop
        inds = np.random.choice(self.targets.shape[0],int(round(self.fraction*self.targets.shape[0])))
        aug_inputs = self.transform(np.array([self.inputs[i,:] for i in inds]))
        self.inputs = np.concatenate([self.inputs,aug_inputs])
        self.targets = np.concatenate([self.targets,[self.targets[i] for i in inds]])
        self._update_num_batches()
        self.shuffle_order = shuffle_order
        self._current_order = np.arange(self.inputs.shape[0])

    def transform(self,aug_inputs):
        aug_inputs = np.multiply(aug_inputs,np.random.choice(2,aug_inputs.shape,p=[self.pdrop,1-self.pdrop]))
        return aug_inputs + np.random.normal(0, self.std, aug_inputs.shape)

class AugmentedMSD25DataProvider(MSD25GenreDataProvider):
    """Data provider for MNIST dataset which transforms images using a variety of possible autoencoders (potentially) trained with added noise"""

    def __init__(self, which_set='train', batch_size=50, max_num_batches=-1,
                 shuffle_order=True, rng=rng,fraction=0.25,std=0.05,pdrop=0.2):
        """Create a new augmented MNIST data provider object.

        Args:
            which_set: One of 'train', 'valid' or 'test'. Determines which
                portion of the MNIST data this object should provide.
            batch_size (int): Number of data points to include in each batch.
            max_num_batches (int): Maximum number of batches to iterate over
                in an epoch. If `max_num_batches * batch_size > num_data` then
                only as many batches as the data can be split into will be
                used. If set to -1 all of the data will be used.
            shuffle_order (bool): Whether to randomly permute the order of
                the data before each epoch.
            rng (RandomState): A seeded random number generator.
            transformer: Function which takes an `inputs` array of shape
                (batch_size, input_dim) corresponding to a batch of input
                images and a `rng` random number generator object (i.e. a
                call signature `transformer(inputs, rng)`) and applies a
                potentiall random set of transformations to some / all of the
                input images as each new batch is returned when iterating over
                the data provider.
        """
        super(AugmentedMSD25DataProvider,self).__init__(
            which_set, batch_size, max_num_batches, shuffle_order, rng)
        self.fraction = fraction
        self.std = std
        self.pdrop = pdrop

        inds = np.random.choice(self.targets.shape[0],int(round(self.fraction*self.targets.shape[0])))
        aug_inputs = self.transform(np.array([self.inputs[i,:] for i in inds]))
        self.inputs = np.concatenate([self.inputs,aug_inputs])
        self.targets = np.concatenate([self.targets,[self.targets[i] for i in inds]])
        self._update_num_batches()
        self.shuffle_order = shuffle_order
        self._current_order = np.arange(self.inputs.shape[0])

    def transform(self,aug_inputs):
        aug_inputs = np.multiply(aug_inputs,np.random.choice(2,aug_inputs.shape,p=[self.pdrop,1-self.pdrop]))
        return aug_inputs + np.random.normal(0, self.std, aug_inputs.shape)
