import tensorflow as tf
import os
import numpy as np
from mlp.data_providers import MSD10GenreDataProvider,MSD25GenreDataProvider
import matplotlib.pyplot as plt
import time
import seaborn as sns
import pandas as pd
from providers import AugmentedMSD10DataProvider,AugmentedMSD25DataProvider
from rnn_providers import TestMSD10DataProvider
from tensorflow.python.ops import rnn, rnn_cell
seed = 123
batch_size = 50
rng = np.random.RandomState(seed)
directory = '../../saved_models/'
class RNN_Model(object):

    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,lam=1e-3):
        self.batch_size = batch_size
        if provider == 0:
            self.output_dim = 10
            self.train_data = MSD10GenreDataProvider('train', batch_size=self.batch_size, rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=batch_size, rng=rng)
        else:
            self.output_dim = 25
            self.train_data = MSD25GenreDataProvider('train', batch_size=self.batch_size, rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=self.batch_size, rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.lr = lr
        self.out = out
        self.lam = lam
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_LR_' + str(self.lr)
        else:
            self.title = title
        self.graph_gen()
    
    def graph_gen(self):
        tf.reset_default_graph()
        self.inputs = tf.placeholder(tf.float32, [None, self.time_steps, self.step_dim], 'inputs')
        self.targets = tf.placeholder(tf.float32, [None, self.num_outputs], 'targets')
        with tf.name_scope('fc-layer'):
            self.hidden = self.RNN_layer(self.inputs)
        with tf.name_scope('output-layer'):
            self.outputs = self.fully_connected_layer(self.hidden, self.num_hidden, self.num_outputs, tf.identity)
        self.learning_functions()


    def RNN_layer(self,inputs,nonlinearity=tf.nn.relu):
        inputs = tf.transpose(inputs, [1, 0, 2])
        inputs = tf.reshape(inputs, [-1,self.step_dim])
        inputs = tf.split(0,self.time_steps,inputs)
        lstm_cell = rnn_cell.BasicLSTMCell(self.num_hidden, forget_bias=1.0)
        with tf.name_scope('lstm'):
            outputs, states = rnn.rnn(lstm_cell, inputs, dtype=tf.float32)
        weights = tf.Variable(
            tf.truncated_normal(
                [self.num_hidden, self.num_hidden], stddev=2. / (self.num_hidden*2)**0.5,seed=123),
            'weights_rec')
        biases = tf.Variable(tf.zeros([self.num_hidden]), 'biases')
        outputs = nonlinearity(tf.matmul(outputs[-1], weights) + biases)
        return outputs

    def fully_connected_layer(self,inputs,input_dim,output_dim,nonlinearity=tf.nn.relu):
        weights = tf.Variable(
            tf.truncated_normal(
                [input_dim, output_dim], stddev=2. / (input_dim + output_dim)**0.5,seed=123),
            'weights_norm')
        biases = tf.Variable(tf.zeros([output_dim]), 'biases')
        outputs = nonlinearity(tf.matmul(inputs, weights) + biases)
        return outputs

    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        with tf.name_scope('error'):
            regloss = tf.add_n([ tf.nn.l2_loss(v) for v in tf_vars
                                if not 'biases' in v.name]) * self.lam           
            self.error = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs, self.targets)+regloss)
            
        with tf.name_scope('accuracy'):
            self.accuracy = tf.reduce_mean(tf.cast(
                tf.equal(tf.argmax(self.outputs, 1), tf.argmax(self.targets, 1)),
                tf.float32))
        with tf.name_scope('train'):
            self.train_step = tf.train.AdamOptimizer(self.lr).minimize(self.error)

        self.init = tf.global_variables_initializer()

    def run_session(self):
        if self.out == 1:
            out_file = open(directory + self.title + '.txt','w')
        sess = tf.Session()
        sess.run(self.init)
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(self.num_epochs):
            start_time = time.time()
            running_error = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_accuracy = 0.
            for input_batch, target_batch in self.train_data:
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                _, batch_error, batch_acc = sess.run(
                    [self.train_step, self.error, self.accuracy],
                    feed_dict={self.inputs: input_batch, self.targets: target_batch})
                running_error += batch_error
                running_accuracy += batch_acc
            end_time=time.time()
            run_time=end_time-start_time
            self.times[e]=run_time
            running_error /= self.train_data.num_batches
            running_accuracy /= self.train_data.num_batches

            for input_batch, target_batch in self.valid_data:
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                batch_error, batch_acc = sess.run(
                    [self.error, self.accuracy],
                    feed_dict={self.inputs: input_batch, self.targets: target_batch})
                valid_error += batch_error
                valid_accuracy += batch_acc
            valid_error /= self.valid_data.num_batches
            valid_accuracy /= self.valid_data.num_batches
            if self.out==1:
                toscreen = 'End of epoch {0:02d}: err(train)={1:.2f} acc(train)={2:.2f} run_time={3:.2f}s | err(valid)={4:.2f} acc(valid)={5:.2f}'.format(e + 1, running_error, running_accuracy, run_time,valid_error, valid_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            self.basic_plot()
            out_file.close()
            self.save_data()

    def basic_plot(self):
            fig, (ax_1, ax_2) = plt.subplots(1, 2,figsize=(10,4))
            for d,k in zip([self.errt[:],self.errv[:]],['err(train)', 'err(valid)']):
                ax_1.plot(np.arange(1, self.num_epochs+1),
                          d, label=k)
            ax_1.set_ylabel('error',visible=True)
            ax_1.set_xlabel('epoch')
            ax_1.legend(loc=0)

            for d,k in zip([self.acct[:],self.accv[:]],['acc(train)', 'acc(valid)']):
                ax_2.plot(np.arange(1, self.num_epochs+1),
                          d, label=k)
            ax_2.set_xlabel('epoch')
            ax_2.set_ylabel('accuracy')
            ax_2.legend(loc=0)
            fig.savefig(directory + self.title +'.pdf',format='pdf')

    def save_data(self):
        big_tensor = np.array([self.acct,self.errt,self.accv,self.acct,self.times])
        np.save(directory+self.title,big_tensor)

class Norm_RNN_Model(RNN_Model):

    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=0.3):
        self.batch_size = batch_size
        if provider == 0:
            self.output_dim = 10
            self.train_data = MSD10GenreDataProvider('train', batch_size=self.batch_size, rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=batch_size, rng=rng)
        else:
            self.output_dim = 25
            self.train_data = MSD25GenreDataProvider('train', batch_size=self.batch_size, rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=self.batch_size, rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.lr = lr
        self.out = out
        self.beta = beta
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_LR_' + str(self.lr)
        else:
            self.title = title
        self.graph_gen()

    def graph_gen(self):
        tf.reset_default_graph()
        self.inputs = tf.placeholder(tf.float32, [None, self.time_steps, self.step_dim], 'inputs')
        self.targets = tf.placeholder(tf.float32, [None, self.num_outputs], 'targets')
        with tf.name_scope('fc-layer'):
            self.hidden,self.out_norm = self.RNN_layer(self.inputs)
        with tf.name_scope('output-layer'):
            self.outputs = self.fully_connected_layer(self.hidden, self.num_hidden, self.num_outputs, tf.identity)
        self.learning_functions()

    def RNN_layer(self,inputs,nonlinearity=tf.nn.relu):
        inputs = tf.transpose(inputs, [1, 0, 2])
        inputs = tf.reshape(inputs, [-1,self.step_dim])
        inputs = tf.split(0,self.time_steps,inputs)
        lstm_cell = rnn_cell.BasicLSTMCell(self.num_hidden, forget_bias=1.0)
        with tf.name_scope('lstm'):
            outputs, states = rnn.rnn(lstm_cell, inputs, dtype=tf.float32)
        weights = tf.Variable(
            tf.truncated_normal(
                [self.num_hidden, self.num_hidden], stddev=2. / (self.num_hidden*2)**0.5,seed=123),
            'weights_rec')
        biases = tf.Variable(tf.zeros([self.num_hidden]), 'biases')
        
        squares = tf.multiply(outputs,outputs)
        c = self.time_steps - 1
        ht1 = tf.slice(squares,begin=[1,0,0],size=[c,-1,self.num_hidden])
        ht2 = tf.slice(squares,begin=[0,0,0],size=[c,-1,self.num_hidden])
        diff = tf.pow(tf.reduce_sum(ht1,axis=2),0.5)
        diff -= tf.pow(tf.reduce_sum(ht2,axis=2),0.5)
        out_norm = tf.reduce_sum(tf.pow(diff,2),0)*self.beta/self.time_steps
        
        outputs = nonlinearity(tf.matmul(outputs[-1], weights) + biases)
        return outputs,out_norm
    
    def tensor_norm(self,tensor):
        return tf.sqrt(tf.reduce_sum(tf.square(tensor), 1, keep_dims=True))

    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        with tf.name_scope('error'):
            self.error = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs, self.targets)+self.out_norm)
        with tf.name_scope('accuracy'):
            self.accuracy = tf.reduce_mean(tf.cast(
                tf.equal(tf.argmax(self.outputs, 1), tf.argmax(self.targets, 1)),
                tf.float32))
        with tf.name_scope('train'):
            self.train_step = tf.train.AdamOptimizer(self.lr).minimize(self.error)

        self.init = tf.global_variables_initializer()
        
class Aug_RNN_Model(Norm_RNN_Model):

    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=100,
                 fraction=0.25,std=0.05,pdrop=0.2):
        super(Aug_RNN_Model,self).__init__(title,num_hidden,lr,num_epochs,provider,out,beta)
        self.fraction=fraction
        self.std=std
        self.pdrop=pdrop
        if provider == 0:
            self.train_data = AugmentedMSD10DataProvider('train', batch_size=50,rng=rng,
                                                         fraction=self.fraction,std=self.std,pdrop=self.pdrop)
        else:
            self.train_data = AugmentedMSD25DataProvider('train', batch_size=50,rng=rng,
                                                         fraction=self.fraction,std=self.std,pdrop=self.pdrop)

class MultiAuto_RNN_Model(Norm_RNN_Model):

    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=100,outputs=10,alpha=0.5):
        if provider == 0:
            self.train_data = MSD10GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=50,rng=rng)
        else:
            self.train_data = MSD25GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=50,rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.lr = lr
        self.beta = beta
        self.out = out
        self.alpha = alpha
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_MultiAuto'+str(int(alpha*10))
        else:
            self.title = title
        self.graph_gen()
            
    def graph_gen(self):
        tf.reset_default_graph()
        self.inputs = tf.placeholder(tf.float32, [None, self.time_steps, self.step_dim], 'inputs')
        self.targets_1 = tf.placeholder(tf.float32, [None, self.train_data.num_classes], 'targets_1')
        self.targets_2 = tf.placeholder(tf.float32, [None, self.time_steps*self.step_dim], 'targets_2')
        with tf.name_scope('fc-layer'):
            self.hidden,self.out_norm = self.RNN_layer(self.inputs)
        with tf.name_scope('output-layer'):
            self.outputs_1 = self.fully_connected_layer(self.hidden, self.num_hidden, self.num_outputs, tf.identity)
            self.outputs_2 = self.fully_connected_layer(self.hidden, self.num_hidden, self.time_steps*self.step_dim,
                                                        tf.identity)
        self.learning_functions()
        

    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        with tf.name_scope('error'):
            self.error2 = tf.reduce_mean(tf.pow(self.outputs_2 - self.targets_2, 2))
            self.error1 = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs_1, self.targets_1)+self.out_norm)
            self.error = self.error1+self.error2*self.alpha
        with tf.name_scope('accuracy'):
            self.accuracy = tf.reduce_mean(tf.cast(
                tf.equal(tf.argmax(self.outputs_1, 1), tf.argmax(self.targets_1, 1)),
                tf.float32))
        with tf.name_scope('train'):
            self.train_step = tf.train.AdamOptimizer(self.lr).minimize(self.error)

        self.init = tf.global_variables_initializer()

    def run_session(self):
        if self.out == 1:
            out_file = open(directory + self.title + '.txt','w')
        sess = tf.Session()
        sess.run(self.init)
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.errt2 = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.errv2 = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(self.num_epochs):
            start_time = time.time()
            running_error = 0.
            running_error2 = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_error2 = 0.
            valid_accuracy = 0.
            for input_batch, target_batch1 in self.train_data:
                target_batch2 = input_batch[:]
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                _, batch_error1, _, batch_acc, batch_error2 = sess.run(
                    [self.train_step,self.error1, self.error, self.accuracy, self.error2],
                    feed_dict={self.inputs: input_batch, self.targets_1: target_batch1, self.targets_2: target_batch2})
                running_error += batch_error1
                running_error2 += batch_error2
                running_accuracy += batch_acc
            end_time=time.time()
            run_time=end_time-start_time
            self.times[e]=run_time
            running_error /= self.train_data.num_batches
            running_error2 /= self.train_data.num_batches
            running_accuracy /= self.train_data.num_batches

            for input_batch, target_batch1 in self.valid_data:
                target_batch2 = input_batch[:]
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                batch_error1, batch_acc, batch_error2 = sess.run(
                    [self.error1, self.accuracy, self.error2],
                    feed_dict={self.inputs: input_batch, self.targets_1: target_batch1, self.targets_2: target_batch2})
                valid_error += batch_error1
                valid_error2 += batch_error2
                valid_accuracy += batch_acc
            valid_error /= self.valid_data.num_batches
            valid_error2 /= self.valid_data.num_batches
            valid_accuracy /= self.valid_data.num_batches
            if self.out==1:
                toscreen = 'End of epoch {0:02d}: err(tr)={1:.2f} acc(train)={2:.2f} err2={3:.2f} run_time={4:.2f}s | err(v)={5:.2f} acc(valid)={6:.2f}'.format(e + 1, running_error, running_accuracy,running_error2, run_time,valid_error, valid_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
            self.errt2[e]=running_error2
            self.errv2[e]=valid_error2
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            self.basic_plot()
            out_file.close()
            self.save_data()
            
    def save_data(self):
        big_tensor = np.array([self.acct,self.errt,self.accv,self.acct,self.times,self.errt2,self.errv2])
        np.save(directory+self.title,big_tensor)

class MultiClass_RNN_Model(Norm_RNN_Model):

    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=100,outputs=10,alpha=0.5):
        if provider == 0:
            self.train_data = MSD10GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=50,rng=rng)
        else:
            self.train_data = MSD25GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=50,rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.beta = beta
        self.lr = lr
        self.out = out
        self.alpha = alpha
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_MultiClass'+str(int(alpha*10))
        else:
            self.title = title
        self.graph_gen()
            
    def graph_gen(self):
        self.targets_2 = []
        self.outputs_2 = []
        tf.reset_default_graph()
        self.inputs = tf.placeholder(tf.float32, [None, self.time_steps, self.step_dim], 'inputs')
        self.targets_1 = tf.placeholder(tf.float32, [None, self.train_data.num_classes], 'targets_1')
        for i in range(self.train_data.num_classes):
            self.targets_2.append(tf.placeholder(tf.float32, [None, 2], 'targets_2_'+str(i)))
        with tf.name_scope('fc-layer'):
            self.hidden, self.out_norm = self.RNN_layer(self.inputs)
        with tf.name_scope('output-layer'):
            self.outputs_1 = self.fully_connected_layer(self.hidden, self.num_hidden, self.num_outputs, tf.identity)
            for i in range(self.train_data.num_classes):
                self.outputs_2.append(self.fully_connected_layer(self.hidden, self.num_hidden, 2,
                                                                 tf.identity))
        self.learning_functions()
        

    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        self.error2 = []
        with tf.name_scope('error'):
            for i in range(self.train_data.num_classes):
                self.error2.append(tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs_2[i],
                                                                                          self.targets_2[i])))
            self.error2 = tf.add_n(self.error2)
            self.error1 = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs_1, self.targets_1)+self.out_norm)
            self.error = self.error1+self.error2*self.alpha
        with tf.name_scope('accuracy'):
            self.accuracy = tf.reduce_mean(tf.cast(
                tf.equal(tf.argmax(self.outputs_1, 1), tf.argmax(self.targets_1, 1)),
                tf.float32))
        with tf.name_scope('train'):
            self.train_step = tf.train.AdamOptimizer(self.lr).minimize(self.error)

        self.init = tf.global_variables_initializer()

    def run_session(self):
        if self.out == 1:
            out_file = open(directory + self.title + '.txt','w')
        sess = tf.Session()
        sess.run(self.init)
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.errt2 = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.errv2 = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(self.num_epochs):
            start_time = time.time()
            running_error = 0.
            running_error2 = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_error2 = 0.
            valid_accuracy = 0.
            for input_batch, target_batch1 in self.train_data:
                system_dict = {}
                for i in range(self.train_data.num_classes):
                    system_dict[self.targets_2[i]] =  np.transpose(np.array([target_batch1[:,i],
                                                                             np.logical_not(target_batch1[:,i])]))
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                system_dict[self.inputs] = input_batch
                system_dict[self.targets_1] = target_batch1
                _, batch_error1, _, batch_acc, batch_error2 = sess.run(
                    [self.train_step,self.error1, self.error, self.accuracy, self.error2],
                    feed_dict=system_dict)
                running_error += batch_error1
                running_error2 += batch_error2
                running_accuracy += batch_acc
            end_time=time.time()
            run_time=end_time-start_time
            self.times[e]=run_time
            running_error /= self.train_data.num_batches
            running_error2 /= self.train_data.num_batches
            running_accuracy /= self.train_data.num_batches

            for input_batch, target_batch1 in self.valid_data:
                system_dict = {}
                for i in range(self.train_data.num_classes):
                    system_dict[self.targets_2[i]] =  np.transpose(np.array([target_batch1[:,i],
                                                                             np.logical_not(target_batch1[:,i])]))
                input_batch = input_batch.reshape((batch_size, self.time_steps, self.step_dim))
                system_dict[self.inputs] = input_batch
                system_dict[self.targets_1] = target_batch1
                batch_error1, batch_acc, batch_error2 = sess.run(
                    [self.error1, self.accuracy, self.error2],
                    feed_dict=system_dict)
                valid_error += batch_error1
                valid_error2 += batch_error2
                valid_accuracy += batch_acc
            valid_error /= self.valid_data.num_batches
            valid_error2 /= self.valid_data.num_batches
            valid_accuracy /= self.valid_data.num_batches
            if self.out==1:
                toscreen = 'End of epoch {0:02d}: err(tr)={1:.2f} acc(train)={2:.2f} err2={3:.2f} run_time={4:.2f}s | err(v)={5:.2f} acc(valid)={6:.2f}'.format(e + 1, running_error, running_accuracy,running_error2, run_time,valid_error, valid_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
            self.errt2[e]=running_error2
            self.errv2[e]=valid_error2
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            self.basic_plot()
            out_file.close()
            self.save_data()
            
    def save_data(self):
        big_tensor = np.array([self.acct,self.errt,self.accv,self.acct,self.times,self.errt2,self.errv2])
        np.save(directory+self.title,big_tensor)



class Ens_RNN_Model(Norm_RNN_Model):
    
    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=100,outputs=10,div=2,method=0):
        if provider == 0:
            self.train_data = MSD10GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=50,rng=rng)
        else:
            self.train_data = MSD25GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=50,rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.method = method
        self.lr = lr
        self.out = out
        self.div = div
        self.part = self.time_steps/self.div
        self.partu = self.num_hidden/self.div
        self.beta = beta
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_Ensemble'+str(int(self.div))
        else:
            self.title = title
        self.graph_gen()
    
    def RNN_layer(self,inputs,i,nonlinearity=tf.nn.relu):
        inputs = tf.transpose(inputs, [1, 0, 2])
        inputs = tf.reshape(inputs, [-1,self.step_dim])
        inputs = tf.split(0,self.part,inputs)
        with tf.variable_scope('lstm'+str(i)):
            lstm_cell = rnn_cell.BasicLSTMCell(self.partu,forget_bias=1.0)
        with tf.variable_scope('lstm_extra'+str(i)):
            outputs, states = rnn.rnn(lstm_cell, inputs, dtype=tf.float32)
            weights = tf.Variable(
                tf.truncated_normal(
                    [self.partu, self.partu], stddev=2. / (self.partu*2)**0.5,seed=123),
                'weights_rec'+str(i))
            biases = tf.Variable(tf.zeros([self.partu]), 'biases')
            
            squares = tf.multiply(outputs,outputs)
            c = self.part - 1
            ht1 = tf.slice(squares,begin=[1,0,0],size=[c,-1,self.partu])
            ht2 = tf.slice(squares,begin=[0,0,0],size=[c,-1,self.partu])
            diff = tf.pow(tf.reduce_sum(ht1,axis=2),0.5)
            diff -= tf.pow(tf.reduce_sum(ht2,axis=2),0.5)
            out_norm = tf.reduce_sum(tf.pow(diff,2),0)*self.beta/self.part
            
            outputs = nonlinearity(tf.matmul(outputs[-1], weights) + biases)
        return outputs,out_norm
    
    def graph_gen(self):
        tf.reset_default_graph()
        self.outputs = []
        self.inputs = []
        self.out_norms = {}
        self.targets = tf.placeholder(tf.float32, [None, self.train_data.num_classes], 'targets')
        for i in range(self.div):
            self.inputs.append(tf.placeholder(tf.float32, [None, self.part, self.step_dim], 'inputs'+str(i)))
            self.hidden, self.out_norms[i] = self.RNN_layer(self.inputs[i],i)
            with tf.name_scope('outputs-layer'):
                self.outputs.append(self.fully_connected_layer(self.hidden, self.partu, self.num_outputs, tf.identity))
        self.learning_functions()

    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        self.error = 0.
        self.errors = np.zeros(self.div).tolist()
        with tf.name_scope('error'):
            self.expert_weights = []
#            weighted_outputs = self.outputs[:]
            for i in range(self.div):
                temp_error = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs[i], self.targets)
                                            +self.out_norms[i])
                self.outputs[i] = tf.nn.softmax(self.outputs[i])
#                weighted_outputs[i]*=tf.pow(temp_error,-1)
                self.error += temp_error
                self.errors[i] += temp_error
            self.error/=self.div
            if self.method == 0:
                probs = tf.add_n(self.outputs)
            else:
                probs = 1.
                for i in range(self.div):
                    probs*=self.outputs[i]
            self.errorp = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(probs,self.targets))        
        
        with tf.name_scope('accuracy'):
            if self.method == 0:
                self.accuracy = tf.reduce_mean(tf.cast(
                        tf.equal(tf.argmax(tf.add_n(self.outputs), 1), tf.argmax(self.targets, 1)),
                        tf.float32))
            else:
                probs = 1.
                for i in range(self.div):
                    probs*=self.outputs[i]
                self.accuracy = tf.reduce_mean(tf.cast(
                        tf.equal(tf.argmax(probs, 1), tf.argmax(self.targets, 1)),
                        tf.float32))
        with tf.name_scope('train'):
            self.trainers = {}
            for i in range(self.div):
                self.trainers[i] = tf.train.AdamOptimizer(self.lr).minimize(self.errors[i])
            

        self.init = tf.global_variables_initializer()
    
    def run_session(self):
        if self.out == 1:
            out_file = open(directory + self.title + '.txt','w')
        sess = tf.Session()
        sess.run(self.init)
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(self.num_epochs):
            start_time = time.time()
            running_error = 0.
            running_error2 = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_error2 = 0.
            valid_accuracy = 0.
            for input_batch, target_batch in self.train_data:
                input_batch = input_batch.reshape((batch_size,self.div,self.part, self.step_dim))
                output_dict = {}
                output_dict[self.targets] = target_batch
                system_dict = {}
                system_dict[self.targets] = target_batch
                for i in range(self.div):
                    system_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    _,output_dict[self.outputs[i]] = sess.run([self.trainers[i],self.outputs[i]],feed_dict=system_dict)
                batch_error, batch_acc = sess.run([self.errorp, self.accuracy],feed_dict=output_dict)
                running_error += batch_error
                running_accuracy += batch_acc
            end_time=time.time()
            run_time=end_time-start_time
            self.times[e]=run_time
            running_error /= self.train_data.num_batches
            running_error2 /= self.train_data.num_batches
            running_accuracy /= self.train_data.num_batches

            for input_batch, target_batch in self.valid_data:
                input_batch = input_batch.reshape((batch_size,self.div,self.part, self.step_dim))
                output_dict = {}
                output_dict[self.targets] = target_batch
                system_dict = {}
                system_dict[self.targets] = target_batch
                for i in range(self.div):
                    system_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.outputs[i]] = sess.run(self.outputs[i],feed_dict=system_dict)
                batch_error, batch_acc = sess.run([self.errorp, self.accuracy],feed_dict=output_dict)
                valid_error += batch_error
                valid_accuracy += batch_acc
            valid_error /= self.valid_data.num_batches
            valid_accuracy /= self.valid_data.num_batches
            if self.out==1:
                toscreen = 'End of epoch {0:02d}: err(train)={1:.2f} acc(train)={2:.2f} run_time={3:.2f}s | err(valid)={4:.2f} acc(valid)={5:.2f}'.format(e + 1, running_error, running_accuracy, run_time,valid_error, valid_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            self.basic_plot()
            out_file.close()
            self.save_data()

#Testing Code
        self.test_data = TestMSD10DataProvider('train', batch_size=50,rng=rng)
        test_error = 0.
        test_accuracy = 0.
        if self.out == 1:
            out_file = open(directory + self.title + '_test' + '.txt','w')
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(1):
            start_time = time.time()
            running_error = 0.
            running_error2 = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_error2 = 0.
            valid_accuracy = 0.
            for input_batch, target_batch in self.test_data:
                input_batch = input_batch.reshape((batch_size,self.div,self.part, self.step_dim))
                output_dict = {}
                output_dict[self.targets] = target_batch
                system_dict = {}
                system_dict[self.targets] = target_batch
                for i in range(self.div):
                    system_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.outputs[i]] = sess.run(self.outputs[i],feed_dict=system_dict)
                batch_error, batch_acc = sess.run([self.errorp, self.accuracy],feed_dict=output_dict)
                test_error += batch_error
                test_accuracy += batch_acc
            test_error /= self.test_data.num_batches
            test_accuracy /= self.test_data.num_batches
            if self.out==1:
                toscreen = 'End of test: err(test)={0:.2f} acc(test)={1:.2f}'.format(test_error, test_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            out_file.close()
            
    def save_data(self):
        big_tensor = np.array([self.acct,self.errt,self.accv,self.acct,self.times])
        np.save(directory+self.title,big_tensor)
        
class EnsL_RNN_Model(RNN_Model):
    
    def __init__(self,title='',num_hidden=200,lr=1e-3,num_epochs=10,provider=0,out=1,beta=100,div=2,method=0):
        if provider == 0:
            self.train_data = MSD10GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD10GenreDataProvider('valid', batch_size=50,rng=rng)
        else:
            self.train_data = MSD25GenreDataProvider('train', batch_size=50,rng=rng)
            self.valid_data = MSD25GenreDataProvider('valid', batch_size=50,rng=rng)
        self.time_steps = 120
        self.step_dim = 25
        self.num_hidden = num_hidden
        self.num_epochs = num_epochs
        self.lr = lr
        self.out = out
        self.div = div
        self.beta = beta
        self.part = self.time_steps/self.div
        self.partu = self.num_hidden/self.div
        self.method = method
        if self.out:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.out = out
        self.num_outputs = self.train_data.num_classes
        if provider == 0:
            self.MSD = 'RNN_MSD10 '
        else:
            self.MSD = 'RNN_MSD25 '
        if title == '':
            self.title = self.MSD + '_Ensemble'+str(int(self.div))
        else:
            self.title = title
        self.graph_gen()


    def RNN_layer(self,inputs,i,nonlinearity=tf.nn.relu):
        inputs = tf.transpose(inputs, [1, 0, 2])
        inputs = tf.reshape(inputs, [-1,self.step_dim])
        inputs = tf.split(0,self.part,inputs)
        with tf.variable_scope('lstm'+str(i)):
            lstm_cell = rnn_cell.BasicLSTMCell(self.partu,forget_bias=1.0)
        with tf.variable_scope('lstm_extra'+str(i)):
            outputs, states = rnn.rnn(lstm_cell, inputs, dtype=tf.float32)
            weights = tf.Variable(
                tf.truncated_normal(
                    [self.partu, self.partu], stddev=2. / (self.partu*2)**0.5,seed=123),
                'weights_rec'+str(i))
            biases = tf.Variable(tf.zeros([self.partu]), 'biases')
            
            squares = tf.multiply(outputs,outputs)
            c = self.part - 1
            ht1 = tf.slice(squares,begin=[1,0,0],size=[c,-1,self.partu])
            ht2 = tf.slice(squares,begin=[0,0,0],size=[c,-1,self.partu])
            diff = tf.pow(tf.reduce_sum(ht1,axis=2),0.5)
            diff -= tf.pow(tf.reduce_sum(ht2,axis=2),0.5)
            out_norm = tf.reduce_sum(tf.pow(diff,2),0)*self.beta/self.part
            
            outputs = nonlinearity(tf.matmul(outputs[-1], weights) + biases)
        return outputs,out_norm
 
    def combiner_layer(self,prediction_list):
        outputs = 0.
        final_prediction = 0.
        for i in range(self.div):
            weight_i = tf.Variable(
            tf.truncated_normal(
                [1, 1], stddev=2. / (2)**0.5,seed=123),
            'weight_i')
            final_prediction += tf.multiply(prediction_list[i], weight_i)
        return final_prediction/self.div
    
    def graph_gen(self):
        tf.reset_default_graph()
        self.outputs = []
        self.inputs = []
        self.out_norms = {}
        self.targets = tf.placeholder(tf.float32, [None, self.train_data.num_classes], 'targets')
        for i in range(self.div):
            self.inputs.append(tf.placeholder(tf.float32, [None, self.part, self.step_dim], 'inputs'+str(i)))
            self.hidden, self.out_norms[i] = self.RNN_layer(self.inputs[i],i)
            with tf.name_scope('outputs-layer'):
                self.outputs.append(self.fully_connected_layer(self.hidden, self.partu, self.num_outputs, tf.identity))
        with tf.name_scope('combined-layer'):
            print len(self.outputs)
            self.combined_output = self.combiner_layer(self.outputs)
        self.learning_functions()
        
    def learning_functions(self):
        tf_vars   = tf.trainable_variables()
        self.error = 0.
        self.errorp = 0.
        self.errors = np.zeros(self.div).tolist()
        with tf.name_scope('error'):
            self.expert_weights = []
#            weighted_outputs = self.outputs[:]
            for i in range(self.div):
                temp_error = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.outputs[i], self.targets)
                                            +self.out_norms[i])
                self.outputs[i] = tf.nn.softmax(self.outputs[i])
#                weighted_outputs[i]*=tf.pow(temp_error,-1)
                self.error += temp_error
                self.errors[i] += temp_error
                
            self.error/=self.div
            self.errorp = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.combined_output, self.targets))
            reglossp = tf.add_n([ tf.nn.l2_loss(v) for v in tf_vars
                                if 'combined' in v.name]) * 1e-3
            self.errorp += reglossp
        
        with tf.name_scope('accuracy'):
            self.accuracy = tf.reduce_mean(tf.cast(
                    tf.equal(tf.argmax(self.combined_output, 1), tf.argmax(self.targets, 1)),
                    tf.float32))
        with tf.name_scope('train'):
            self.train_combiner = tf.train.AdamOptimizer(self.lr).minimize(self.errorp)
            self.trainers = {}
            for i in range(self.div):
                self.trainers[i] = tf.train.AdamOptimizer(self.lr).minimize(self.errors[i])

        self.init = tf.global_variables_initializer()
        
    def run_session(self):
        if self.out == 1:
            out_file = open(directory + self.title + '.txt','w')
        sess = tf.Session()
        sess.run(self.init)
        self.acct = np.zeros(self.num_epochs)
        self.errt = np.zeros(self.num_epochs)
        self.accv = np.zeros(self.num_epochs)
        self.errv = np.zeros(self.num_epochs)
        self.times = np.zeros(self.num_epochs)
        for e in range(self.num_epochs):
            start_time = time.time()
            running_error = 0.
            running_error2 = 0.
            running_accuracy = 0.
            valid_error = 0.
            valid_error2 = 0.
            valid_accuracy = 0.
            for input_batch, target_batch in self.train_data:
                input_batch = input_batch.reshape((batch_size,self.div,self.part, self.step_dim))
                output_dict = {}
                output_dict[self.targets] = target_batch
                system_dict = {}
                system_dict[self.targets] = target_batch
                for i in range(self.div):
                    system_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    _,output_dict[self.outputs[i]] = sess.run([self.trainers[i],self.outputs[i]],feed_dict=system_dict)
                _, batch_error, batch_acc = sess.run([self.train_combiner,self.errorp, self.accuracy],feed_dict=output_dict)
                running_error += batch_error
                running_accuracy += batch_acc
            end_time=time.time()
            run_time=end_time-start_time
            self.times[e]=run_time
            running_error /= self.train_data.num_batches
            running_error2 /= self.train_data.num_batches
            running_accuracy /= self.train_data.num_batches

            for input_batch, target_batch in self.valid_data:
                input_batch = input_batch.reshape((batch_size,self.div,self.part, self.step_dim))
                output_dict = {}
                output_dict[self.targets] = target_batch
                system_dict = {}
                system_dict[self.targets] = target_batch
                for i in range(self.div):
                    system_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.inputs[i]] = input_batch[:,i,:,:]
                    output_dict[self.outputs[i]] = sess.run(self.outputs[i],feed_dict=system_dict)
                batch_error, batch_acc = sess.run([self.errorp, self.accuracy],feed_dict=output_dict)
                valid_error += batch_error
                valid_accuracy += batch_acc
            valid_error /= self.valid_data.num_batches
            valid_accuracy /= self.valid_data.num_batches
            if self.out==1:
                toscreen = 'End of epoch {0:02d}: err(train)={1:.2f} acc(train)={2:.2f} run_time={3:.2f}s | err(valid)={4:.2f} acc(valid)={5:.2f}'.format(e + 1, running_error, running_accuracy, run_time,valid_error, valid_accuracy)
                print(toscreen)
                out_file.write(toscreen + '\n')

            self.errt[e]=(running_error)
            self.errv[e]=(valid_error)
            self.acct[e]=(running_accuracy)
            self.accv[e]=(valid_accuracy)
        self.avg_time,self.min_err,self.max_acc=np.mean(self.times),np.min(self.errv),np.max(self.accv)
        if self.out==1:
            print('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc))
            out_file.write(('{0:s} Done! Avg. Epoch Time: {1:.2f}s, Best Val. Error: {2:.2f}, Best Val. Accuracy: {3:.2f}\n'.format(
                    self.title,self.avg_time,self.min_err,self.max_acc)))
            self.basic_plot()
            out_file.close()
            self.save_data()
            
    def save_data(self):
        big_tensor = np.array([self.acct,self.errt,self.accv,self.acct,self.times])
        np.save(directory+self.title,big_tensor)
        
        
class MultiPlot(object):
    def __init__(self,sims,labels):
        self.sims = sims
        self.d1 = len(sims)
        self.d2 = len(sims[0][:])
        self.datlen = len(sims[0][0][0,:])
        self.labels = labels
        self.times = np.zeros([self.d1,self.d2])
        self.errs = np.zeros([self.d1,self.d2])
        self.accs = np.zeros([self.d1,self.d2])
        for k in range(self.d1):
            for j in range(self.d2):
                self.times[k,j]=np.mean(self.sims[k][j][-1,:])
                self.accs[k,j]=np.max(self.sims[k][j][2,:])

    def acc_grid(self):
        fig, axarr = plt.subplots(self.d1, self.d2,figsize=(16,8))
        for k in range(self.d1):
            axarr[k,0].set_ylabel('accuracy')
            for j in range(self.d2):
                for d,w in zip([self.sims[k][j][0,:],self.sims[k][j][2,:]],['acc(train)', 'acc(valid)']):
                    axarr[k,j].plot(np.arange(1, self.datlen+1),
                              d, label=w)
                if k!=self.d1-1:
                    plt.setp(axarr[k,j].get_xticklabels(), visible=False)
                else:
                    axarr[k][j].set_xlabel('epoch')
        axarr[0,0].legend(loc=0)
        fig.get_figure().savefig('agrid{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')

    def time_heat(self,rs,cs):
        rs = [str(rs[i]) for i in range(self.d1)]
        cs = [str(cs[i]) for i in range(self.d2)]
        times = pd.DataFrame(self.times,index=rs,columns=cs)
        fig = sns.heatmap(times, annot=True)
        fig.set(xlabel=self.labels[0], ylabel=self.labels[1])
        fig.get_figure().savefig('theat{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')

    def acc_heat(self,rs,cs):
        rs = [str(rs[i]) for i in range(self.d1)]
        cs = [str(cs[i]) for i in range(self.d2)]
        accs = pd.DataFrame(self.accs,index=rs,columns=cs)
        fig = sns.heatmap(accs, annot=True)
        fig.set(xlabel=self.labels[0], ylabel=self.labels[1])
        fig.get_figure().savefig('aheat{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')
    
    def acc_curves(self,titles):
        fig = plt.figure()
        for k in range(self.d1):
            for j in range(self.d2):
                plt.plot(np.arange(1,self.datlen+1),self.sims[k][j][2,:],label=titles[k][j])
        plt.legend(loc=0)
        plt.ylabel('accuracy')
        plt.xlabel('epoch')
        plt.show()
        fig.savefig('acc{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')

    def err2_curves(self,titles):
        fig = plt.figure()
        for k in range(self.d1):
            for j in range(self.d2):
                plt.plot(np.arange(1,self.datlen+1),self.sims[k][j][-2,:],label=titles[k][j])
        plt.legend(loc=0)
        plt.ylabel('sec. error')
        plt.xlabel('epoch')
        plt.show()
        fig.savefig('acc{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')
        
    def err_curves(self,titles):
        fig = plt.figure()
        for k in range(self.d1):
            for j in range(self.d2):
                plt.plot(np.arange(1,self.datlen+1),self.sims[k][j][1,:],label=titles[k][j])
        plt.legend(loc=0)
        plt.ylabel('error')
        plt.xlabel('epoch')
        plt.show()
        fig.savefig('acc{0}_{1}.pdf'.format(self.labels[0],self.labels[1]),format='pdf')

class DataLoader(object):
    def __init__(self,filename,labels):
        self.the_big_tensor = np.load(filename)
        for k in range(self.d1):
            for j in range(self.d2):
                self.times[k][j],self.errs[k][j],self.accs[k][j] = self.the_big_tensor[k,j,0,:],
                self.the_big_tensor[k,j,1,:],self.the_big_tensor[k,j,2,:]
