import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data
import numpy as np
import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os, sys
import skimage.io
sys.path.append('utils')
from nets import *
from datas import *
from sklearn.manifold import TSNE
from ops import *
import argparse

from skimage import img_as_ubyte

# from my_utils import Timer2

d_scale_factor = 0.25
g_scale_factor = 1 - 0.75 / 2

import ignored_config as iconfig
closer_look_path = iconfig.closer_look_path

DEBUG = False

def sample_z(m, n, std=1):
    # return np.random.uniform(-1., 1., size=[m, n])
    return np.random.normal(0, std, size=[m, n])

def loss_hinge_dis(dis_f, dis_p, dis_real):
    loss = tf.reduce_mean(tf.nn.relu(1. - dis_real))
    loss += tf.reduce_mean(tf.nn.relu(1. + dis_p))
    loss += tf.reduce_mean(tf.nn.relu(1. + dis_f))
    return loss

def loss_hinge_gen(dis_fake):
    loss = -tf.reduce_mean(dis_fake)
    return loss

def reconstruct_mutual_info(true_continuous, c_continuous, continuous_lambda = 1):
    std_contig = tf.ones_like(c_continuous)
    epsilon = (true_continuous - c_continuous) / (std_contig + 1e-8)
    ll_continuous = continuous_lambda * tf.reduce_sum(
        - 0.5 * np.log(2 * np.pi) - tf.log(std_contig + 1e-8) - 0.5 * tf.square(epsilon),
        reduction_indices=1)
    return ll_continuous

def NLLNormal(x_r, x_f, sigma = 1.0):
    -0.5 * np.log(2 * np.pi) - 1.0/(2.0*(sigma**2)) *tf.square(x_r - x_f)




#def lgm_logits(feat, num_classes, means, covariance, labels=None, alpha=0.1, lambda_=0.01):
#    '''
#    The 3 input hyper-params are explained in the paper.\n
#    Support 2 modes: Train, Validation\n
#    (1)Train:\n
#    return logits, likelihood_reg_loss\n
#    (2)Validation:\n
#    Set labels=None\n
#    return logits\n
#    '''
#    # classification_probability
#    batch_size = feat.shape.as_list()[0]
#    feature_dim = feat.shape.as_list()[1]
#    reshape_var = tf.reshape(covariance, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
#    reshape_mean = tf.reshape(means, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
#    expand_data = tf.expand_dims(feat, 0)  # (1, batch_size, feature_dim)
#    data_mins_mean = expand_data - reshape_mean  # (num_classes, batch_size, feature_dim)
#    pair_m_distance = tf.matmul(data_mins_mean / (reshape_var + 1e-4), data_mins_mean,
#                                transpose_b=True) / 2.0  # (num_classes, batch_size, batch_size)
#    # index = tf.constant([i for i in range(batch_size)])
#    # m_distance = pair_m_distance[:, index, index].T #(batch_size, num_classes)
#    m_distance = tf.transpose(tf.matrix_diag_part(pair_m_distance))
#
#    det = tf.reduce_prod(covariance, axis=1)
#    label_onehot = tf.one_hot(labels, num_classes)
#    adjust_m_distance = m_distance + label_onehot * alpha * m_distance
#    probability = tf.exp(-adjust_m_distance) / (tf.sqrt(det) + 1e-4)
#
#    # likelihood regularization
#    # means_batch = tf.gather(means, labels)
#    var_batch = tf.gather(covariance, labels)  # (batch_size, feature_dim)
#    batch_det = tf.reduce_prod(var_batch, axis=1)
#    class_distance = tf.reduce_sum(label_onehot * m_distance, axis=1)
#    likelihood_loss = lambda_ * (class_distance + tf.log(batch_det + 1e-4) / 2)
#    # likelihood_loss = lambda_ * class_distance
#
#    # classification_loss
#    class_probability = tf.reduce_sum(label_onehot * probability, axis=1)
#    classification_loss = -tf.log(class_probability / (tf.reduce_sum(probability, axis=1) + 1e-4) + 1e-4)
#    print('LGM loss built with alpha=%f, lambda=%f\n' % (alpha, lambda_))
#    return classification_loss, likelihood_loss, probability, m_distance
def lgm_logits(feat, num_classes, means, covariance, labels=None, alpha=0.1, lambda_=0.01):
    '''
    The 3 input hyper-params are explained in the paper.\n
    Support 2 modes: Train, Validation\n
    (1)Train:\n
    return logits, likelihood_reg_loss\n
    (2)Validation:\n
    Set labels=None\n
    return logits\n
    '''
    # classification_probability
    batch_size = feat.shape.as_list()[0]
    feature_dim = feat.shape.as_list()[1]
    reshape_var = tf.reshape(covariance, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
    reshape_mean = tf.reshape(means, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
    expand_data = tf.expand_dims(feat, 0)  # (1, batch_size, feature_dim)
    data_mins_mean = expand_data - reshape_mean  # (num_classes, batch_size, feature_dim)
    pair_m_distance = tf.matmul(data_mins_mean * reshape_var , data_mins_mean,
                                transpose_b=True) / 2.0  # (num_classes, batch_size, batch_size)
    # index = tf.constant([i for i in range(batch_size)])
    # m_distance = pair_m_distance[:, index, index].T #(batch_size, num_classes)
    m_distance = tf.transpose(tf.matrix_diag_part(pair_m_distance))

    det = tf.reduce_prod(covariance, axis=1)
    label_onehot = tf.one_hot(labels, num_classes)
    adjust_m_distance = m_distance + label_onehot * alpha * m_distance
    probability = tf.exp(-adjust_m_distance) * tf.sqrt(det)

    # likelihood regularization
    # means_batch = tf.gather(means, labels)
    var_batch = tf.gather(covariance, labels)  # (batch_size, feature_dim)
    batch_det = tf.reduce_prod(var_batch, axis=1)
    class_distance = tf.reduce_sum(label_onehot * m_distance, axis=1)
    likelihood_loss = lambda_ * (class_distance - tf.log(batch_det + 1e-4) / 2.0)
    # likelihood_loss = lambda_ * class_distance

    # classification_loss
    class_probability = tf.reduce_sum(label_onehot * probability, axis=1)
    classification_loss = -tf.log(class_probability / (tf.reduce_sum(probability, axis=1) + 1e-8) + 1e-4)
    print('LGM loss built with alpha=%f, lambda=%f\n' % (alpha, lambda_))
    return classification_loss, likelihood_loss, probability, m_distance

def lkd_loss(feat, num_classes, means, covariance, labels):
    feature_dim = feat.shape.as_list()[1]
    reshape_var = tf.reshape(covariance, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
    reshape_mean = tf.reshape(means, [-1, 1, feature_dim])  # (num_classes, 1, feature_dim)
    expand_data = tf.expand_dims(feat, 0)  # (1, batch_size, feature_dim)
    data_mins_mean = expand_data - reshape_mean  # (num_classes, batch_size, feature_dim)
    pair_m_distance = tf.matmul(data_mins_mean / (reshape_var + 1e-8), data_mins_mean, transpose_b=True) / 2.0  # (num_classes, batch_size, batch_size)
    m_distance = tf.transpose(tf.matrix_diag_part(pair_m_distance))
    label_onehot = tf.one_hot(labels, num_classes)
    var_batch = tf.gather(covariance, labels)  # (batch_size, feature_dim)
    batch_det = tf.reduce_prod(var_batch, axis=1)
    class_distance = tf.reduce_sum(label_onehot * m_distance, axis=1)
    likelihood_loss = class_distance + tf.log(batch_det + 1e-8) / 2
    return likelihood_loss

def kl_loss(z_mu, z_logvar):
    return 0.5 * tf.reduce_mean(tf.exp(z_logvar) + z_mu ** 2 - 1. - z_logvar, 1)

def kl_loss_mu_sigma_c(z_mu, z_logvar, means_c, variances_c):
    return 0.5 * tf.reduce_mean(tf.exp(z_logvar) / (variances_c + 1e-8) + ((z_mu-means_c)**2) / (variances_c + 1e-8) -1. - z_logvar + tf.log(variances_c + 1e-8), 1)


def gd_loss(f1, f2):
    f1_avg = tf.reduce_mean(f1, axis=0)
    f2_avg = tf.reduce_mean(f2, axis=0)
    return 0.5 * tf.reduce_sum(tf.square(f1_avg - f2_avg))

def sample_z_muvar(mu, log_var):
    eps = tf.random_normal(shape=tf.shape(mu))
    return mu + tf.exp(log_var / 2) * eps


class GMM_AE_GAN():
    def __init__(self, generator, identity, attribute, discriminator, latent_discriminator, data, is_training, log_dir='logs/mnist',
                 model_dir='models/mnist/', learn_rate_init = 2e-4, save_freq=500):
        self.log_vars = []
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.model_dir = model_dir
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)

        # to fix bug (generate all the same), seems not work lollllllll fk
        tf.reset_default_graph()
        
        self.generator = generator
        self.identity = identity
        self.attribute = attribute
        self.discriminator = discriminator
        self.latent_discriminator = latent_discriminator
        self.data = data
        self.learn_rate_init = learn_rate_init
        self.save_freq = save_freq

        self.z_dim = self.data.z_dim # 100
        if hasattr(self.data, 'zc_dim'):
            self.zc_dim = self.data.zc_dim # 32
        else:
            self.zc_dim = self.z_dim

        self.y_dim = self.data.y_dim
        self.size = self.data.size
        self.channel = self.data.channel
        self.lambda1 = 0.05  # KL_loss
        self.lambda2 = 1  # recon_loss

        self.X = tf.placeholder(tf.float32, shape=[None, self.size, self.size, self.channel], name='X')
        self.z_c = tf.placeholder(tf.float32, shape=[None, self.zc_dim], name='z_c')
        self.z_p = tf.placeholder(tf.float32, shape=[None, self.z_dim], name='z_p')
#         self.z_p2 = tf.placeholder(tf.float32, shape=[None, self.z_dim], name='z_p2')
        self.Y = tf.placeholder(tf.int32, shape=[None], name='Y')
        self.Y_onehot = tf.one_hot(self.Y, self.y_dim)
        self.Y_rand = tf.placeholder(tf.int32, shape=[None], name='Y_rand')
        self.Y_rand_onehot = tf.one_hot(self.Y_rand, self.y_dim)
        # self.is_training = tf.placeholder(tf.bool, name='is_training')
        self.is_training = is_training
        # nets

        # Identity (label-relevant encoder?)
        self.z_enc_c, self.means_c, self.variance_c_var, self.covariance_c = self.identity(self.X, self.is_training) # BUGFIX: problem here?

        # self.covariance_c = tf.exp(tf.minimum(self.log_covariance_c, np.log(100)))

        # Attribute (label-irrelevant encoder?)
        self.z_mu, self.z_logvar = self.attribute(self.X, self.is_training)

        # Generator
        # label-irrelevant features
        self.z_enc_p = sample_z_muvar(self.z_mu, self.z_logvar)
        # to adjust decoded image, different label-irrelevant features
        self.lambda_zlogvar = tf.placeholder(tf.float32, shape=(), name='lambda_zlogvar')
        self.z_enc_p2 = sample_z_muvar(self.z_mu, self.z_logvar*self.lambda_zlogvar)
        
        # latent discriminator
        self.c_enc_p = self.latent_discriminator(self.z_enc_p)
        
        # self.z_means_c = tf.gather(self.means_c, self.Y)
        self.G_dec = self.generator(self.z_enc_c, self.z_enc_p, self.is_training)
        
        # reconstructed image that use random label-irrelevant latent vector
        self.G_dec2 = self.generator(self.z_enc_c, self.z_enc_p2, self.is_training, reuse=True)

#        self.z_sample_c = self.z_c * tf.sqrt(tf.gather(self.covariance_c, self.Y_rand)) + tf.gather(self.means_c, self.Y_rand)
        self.z_sample_c = self.z_c / tf.sqrt(tf.gather(self.covariance_c, self.Y_rand)) + tf.gather(self.means_c, self.Y_rand)
        self.G_sample = self.generator(self.z_sample_c, self.z_p, self.is_training, reuse=True)

        self.d_real = self.discriminator(self.X, self.Y_onehot, self.is_training)
        # reconstructed fake images
        self.d_fake_dec = self.discriminator(self.G_dec, self.Y_onehot, self.is_training, reuse=True)
        # fake images from random vector
        self.d_fake_sample = self.discriminator(self.G_sample, self.Y_rand_onehot, self.is_training, reuse=True)

        # GM loss
        self.classification_loss, self.likelihood_reg, _, _ = lgm_logits(self.z_enc_c, self.y_dim, self.means_c,
                                                                         self.covariance_c, self.Y, alpha = 0, lambda_= 0.1)
        # self.sigma_regularizer = tf.contrib.layers.l2_regularizer(1e-5)(self.covariance_c)
        self.GM_loss = tf.reduce_mean(self.classification_loss) + tf.reduce_mean(self.likelihood_reg) # + self.sigma_regularizer
        self.log_vars.append(("GM_loss", self.GM_loss))

        # KL_loss
        self.KL_loss = tf.reduce_mean(kl_loss(self.z_mu, self.z_logvar))
        self.log_vars.append(("KL_loss", self.KL_loss))
        
         # C loss to classify c_enc_p
        self.Y_onehot = tf.one_hot(self.Y, self.y_dim)
        self.C_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels = self.Y_onehot, logits = self.c_enc_p))
        self.log_vars.append(("C_loss", self.C_loss))

        # adversarial loss
        self.adv_Y = tf.ones_like(self.c_enc_p, dtype=tf.float32) / tf.cast(self.y_dim, tf.float32)
        self.adv_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels = self.adv_Y, logits=self.c_enc_p))
        self.log_vars.append(("adv_loss", self.adv_loss))

        # reconstruction loss
        self.rec_loss = L2_loss(self.X, self.G_dec)
        self.log_vars.append(("rec_loss", self.rec_loss))

        # self.vae_loss = self.rec_loss + 0.1*self.KL_loss
        # self.log_vars.append(("vae_loss", self.vae_loss))
        # G loss
        self.g_loss = loss_hinge_gen(self.d_fake_dec) + loss_hinge_gen(self.d_fake_sample)
        self.log_vars.append(("g_loss", self.g_loss))
        # D loss
        self.d_loss = loss_hinge_dis(self.d_fake_dec, self.d_fake_sample, self.d_real)
        self.log_vars.append(("d_loss", self.d_loss))



        # Global step & Learning rate
        # self.global_step = tf.Variable(0, trainable=False)
        # self.add_global = self.global_step.assign_add(1)
        # self.learning_rate = tf.train.exponential_decay(self.learn_rate_init, global_step=self.global_step,
        #                                                 decay_steps=5000, decay_rate=0.95, staircase=True)
        # self.log_vars.append(("lr", self.learning_rate))

        # Optimizer
        self.lr = tf.placeholder(dtype=tf.float32, shape=[])
        self.log_vars.append(("lr", self.lr))
        
        
        
        # TODO: put opt in control_dependencies
#         # G_opt = tf.train.RMSPropOptimizer(learning_rate=self.learning_rate)
#         id_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         variance_opt = tf.train.AdamOptimizer(self.lr, beta1=0, beta2=0.9)
#         id_rec_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         gen_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         dis_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         att_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         adv_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
#         # A_opt = tf.train.RMSPropOptimizer(learning_rate=self.learning_rate)

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):

            
            
            # TODO: which is better?
            # G_opt = tf.train.RMSPropOptimizer(learning_rate=self.learning_rate)
            id_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            variance_opt = tf.train.AdamOptimizer(self.lr, beta1=0, beta2=0.9)
            id_rec_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            gen_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            dis_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            att_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            adv_opt = tf.train.AdamOptimizer(5e-4, beta1=0, beta2=0.9)
            # A_opt = tf.train.RMSPropOptimizer(learning_rate=self.learning_rate)
            
            # self.G_solver = G_opt.minimize(self.lambda2 * self.rec_loss ,
            #                                var_list=self.generator.vars)
            self.id_solver = id_opt.minimize(self.GM_loss, var_list=self.identity.base_layers_vars+[self.means_c])
            self.variance_solver = variance_opt.minimize(self.GM_loss, var_list=[self.variance_c_var])
            self.id_rec_solver = id_rec_opt.minimize(10 * self.rec_loss + 10 * tf.reduce_mean(self.likelihood_reg), var_list=self.identity.base_layers_vars)
            self.att_solver = att_opt.minimize(10 * self.rec_loss + self.KL_loss + self.adv_loss, var_list=self.attribute.vars)
            self.gen_solver = gen_opt.minimize(10 * self.rec_loss + self.g_loss, var_list=self.generator.vars)
            self.dis_solver = dis_opt.minimize(self.d_loss, var_list=self.discriminator.vars)
            self.adv_solver = adv_opt.minimize(self.C_loss, var_list = self.latent_discriminator.vars)

        # Summary
        for k, v in self.log_vars:
            tf.summary.scalar(k, v)
        self.summary_op = tf.summary.merge_all()

        gpu_options = tf.GPUOptions(allow_growth=True)
        self.sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
        self.saver = tf.train.Saver(max_to_keep=30)

    def restore(self, model_step):
        restore_path = os.path.join(self.model_dir, 'model.ckpt-' + str(model_step))
        print('restore from: '+ restore_path)
        self.saver.restore(self.sess, restore_path)
#         self.sess.run(tf.global_variables_initializer()) # should run this line with or without restore
#         try:
#             ckpt = tf.train.get_checkpoint_state(self.model_dir)
#             print('GMM_AE_GAN.model_dir:', self.model_dir)
#             print('Restoring from {}...'.format(ckpt.model_checkpoint_path)) # is that comma typo ???
#             self.saver.restore(self.sess, ckpt.model_checkpoint_path)
#             basename = os.path.basename(ckpt.model_checkpoint_path) # 'model.ckpt-<restore_iter>'
#             stem = os.path.splitext(basename)[1] # '.ckpt-<restore_iter>'
#             restore_iter = int(stem.split('-')[-1])
#             print('done')
#         except:
#             raise 'Check your pretrained {:s}'.format(ckpt.model_checkpoint_path)


    def train(self, sample_folder, training_iters=320001, batch_size=96, restore=False, n_gm = 3, base_lr = 5e-4, eval_model=None):
        
        def generate_samples(gvaegan, X_batch, Y_batch, file_prefix, nr=4, nc=4):
            n_draws=nr*nc
            assert n_draws <= Y_batch.shape[0]
            
            X_samples = X_batch[:n_draws]
            Y_samples = Y_batch[:n_draws]
            feed_dict2 = {
                    # G_sample feed_dict
                    gvaegan.z_c: sample_z(n_draws, gvaegan.zc_dim), 
                    gvaegan.z_p: sample_z(n_draws, gvaegan.z_dim), 
#                     self.z_p2: sample_z(16, self.z_dim, std=1.2), #sample_z(), 
                    gvaegan.lambda_zlogvar: lambda_zlogvar, 
                    gvaegan.Y_rand: np.random.choice(gvaegan.data.y_dim, n_draws), 
                    gvaegan.X: X_samples, 
                    gvaegan.Y: Y_samples, 
                         }
#             samples, rec_samples = gvaegan.sess.run(
#                         [self.G_sample, self.G_dec], 
            samples, rec_samples, rec_samples2 = gvaegan.sess.run(
                [gvaegan.G_sample, gvaegan.G_dec, gvaegan.G_dec2], 
                feed_dict=feed_dict2)

            fig = gvaegan.data.data2fig(samples, nr, nc)
            plt.savefig('{}/{}.png'.format(sample_folder, file_prefix+'gen_rand'), bbox_inches='tight')
            plt.close(fig)

            rec_fig = gvaegan.data.data2fig(rec_samples, nr, nc)
            plt.savefig('{}/{}.png'.format(sample_folder, file_prefix+'rec'), bbox_inches='tight')
            plt.close(rec_fig)

            rec2_fig = gvaegan.data.data2fig(rec_samples2, nr, nc)
            plt.savefig('{}/{}.png'.format(sample_folder, file_prefix+'rec_with_lambda'), bbox_inches='tight')
            plt.close(rec2_fig)

            ori_fig = gvaegan.data.data2fig(X_samples, nr, nc)
            plt.savefig('{}/{}.png'.format(sample_folder, file_prefix+'ori'), bbox_inches='tight')
            plt.close(ori_fig)
        
        self.sess.run(tf.global_variables_initializer()) # should run this line with(?) or without restore
        
        restore_iter = 0
        if restore:
            try:
                # TODO: restore model failed
                ckpt = tf.train.get_checkpoint_state(self.model_dir)
                print('GMM_AE_GAN.model_dir:', self.model_dir)
                print('Restoring from {}...'.format(ckpt.model_checkpoint_path)) # is that comma typo ???
                self.saver.restore(self.sess, ckpt.model_checkpoint_path)
                basename = os.path.basename(ckpt.model_checkpoint_path) # 'model.ckpt-<restore_iter>'
                stem = os.path.splitext(basename)[1] # '.ckpt-<restore_iter>'
                restore_iter = int(stem.split('-')[-1])
                print('done')
                i = restore_iter / 1000
            except:
                raise 'Check your pretrained {:s}'.format(ckpt.model_checkpoint_path)
        
        
        self.summary_writer = tf.summary.FileWriter(self.log_dir, self.sess.graph)

        lambda_zlogvar = 2. # this is useless
        for iter in range(restore_iter, training_iters):
            # learning rate
            lr_ipt = base_lr / (10 ** (iter //(self.data.num_examples // batch_size * 10)))
            
            for _ in range(n_gm):
                X_b, Y_b = self.data(batch_size)
                n_data = Y_b.shape[0] # not necessary to equal batch_size, BUGFIX
#                 z_p2_useless = np.zeros((n_data, self.z_dim))
                feed_dict = {self.X: X_b, self.z_c: sample_z(n_data, self.zc_dim),
                             self.z_p: sample_z(n_data, self.z_dim), self.Y: Y_b,
                             self.Y_rand: np.random.choice(self.y_dim, n_data),
                             self.lr: lr_ipt, 
                             self.lambda_zlogvar: lambda_zlogvar, 
#                              self.z_p2: z_p2_useless, 
                            }
                # GM_loss_curr =  self.sess.run(self.GM_loss, feed_dict=feed_dict)
                self.sess.run([self.id_solver,self.variance_solver], feed_dict=feed_dict)
#             timer('n_gm loop end')
            feed_dict = {self.X: X_b, 
                         self.z_c: sample_z(n_data, self.zc_dim), 
                         self.z_p: sample_z(n_data, self.z_dim),
                         self.Y: Y_b, self.Y_rand: np.random.choice(self.y_dim, n_data), 
                         self.lr:lr_ipt, 
                         self.lambda_zlogvar: lambda_zlogvar, 
#                          self.z_p2: z_p2_useless, 
                        }
            KL_loss_curr = self.sess.run(self.KL_loss, feed_dict=feed_dict)
#             timer('sess.run(KL_loss) end')
            # fetch_list = [self.D_solver, self.G_solver, self.A_solver, self.C_solver, self.summary_op]
            # fetch_list = [self.G_solver, self.A_solver, self.summary_op]
            fetch_list = [self.att_solver, self.gen_solver, self.dis_solver, self.adv_solver, self.id_rec_solver, self.summary_op]
            # fetch_list += [self.D_loss, self.G_loss, self.rec_loss, self.GM_loss, self.KL_loss, self.C_loss, self.neg_mutual_info]
            fetch_list += [ self.rec_loss, self.GM_loss, self.KL_loss, self.C_loss, self.adv_loss, self.g_loss, self.d_loss]
            _, _, _, _, _, summary_str, rec_loss_curr, GM_loss_curr, KL_loss_curr, C_loss_curr, adv_loss_curr, g_loss_curr, d_loss_curr = self.sess.run(fetch_list, feed_dict=feed_dict)

            self.summary_writer.add_summary(summary_str, iter)

            # new_learn_rate = self.sess.run(self.learning_rate)
            # if new_learn_rate > 0.00005:
            #     self.sess.run(self.add_global)

            # print loss. save images.
            if iter % 100 == 0 or iter < 100:
                print('Iter: {}; rec_loss: {:.4}, GM_loss: {:.4}, KL_loss: {:.4}, C_loss: {:.4}, adv_loss: {:.4}, g_loss: {:.4}, d_loss: {:.4}'.format(
                    iter, rec_loss_curr, GM_loss_curr, KL_loss_curr, C_loss_curr, adv_loss_curr, g_loss_curr, d_loss_curr))

            if (iter % self.save_freq == 0) or iter == training_iters - 1:
                save_path = os.path.join(self.model_dir, "model.ckpt")
                self.saver.save(self.sess, save_path, global_step=iter)

                # draw examples
                nr = 5
                nc = 5
                generate_samples(self, X_b, Y_b, file_prefix=str(iter).zfill(7), nr=nr, nc=nc)
                # go to is_training=False mode
                self.set_is_training(is_training=False, resume_iter=iter)
                generate_samples(self, X_b, Y_b, file_prefix=str(iter).zfill(7)+'_eval-', nr=nr, nc=nc)
#                     if eval_model is not None:
#                         generate_samples(eval_model, X_b, Y_b, file_prefix=str(i).zfill(3)+'eval-', n_draws=n_draws)
                # go back to training mode
                self.set_is_training(is_training=True, resume_iter=iter)
                print('finished set back to is_training=True.')

    # TODO: set_is_training
    def set_is_training(self, is_training, resume_iter):
        if self.is_training == is_training:
            print('Warning: LrLiVAE.is_training is already %s, so not changed.'%(str(is_training)))
            return
        
        self.__init__(
            generator=self.generator, identity=self.identity, attribute=self.attribute, 
            discriminator=self.discriminator, latent_discriminator=self.latent_discriminator, 
            data=self.data, is_training=is_training, 
            log_dir=self.log_dir, model_dir=self.model_dir, 
            learn_rate_init = self.learn_rate_init, 
            save_freq = self.save_freq
        )
        self.restore(resume_iter)
        
        
    def check_weights(self, name=None, show=True):
        variables_names = [v.name for v in tf.trainable_variables()] # TODO: not trainable????
        values = self.sess.run(variables_names)
        print('='*10, 'checking weights', '='*10)
        found = False
        for i, (k, v) in enumerate(zip(variables_names, values)):
            if name is None:
                print("Variable: ", k)
                print("Shape: ", v.shape)
                if show:
                    print(v)
            else:
                if name in k:
                    found = True
                    print(k)
                    if show:
                        print(v)
        if name is not None and found==False:
            raise 'no matched trainable variable name.'
    
#     def rec_samples(self, imgs, lambda_zlogvar=1, save_fig=False):
    def rec_samples(self, imgs, lambda_zlogvar=1):
        # should restore or train before calling this function
#         if save_fig: # TODO: save figure
#             if not os.path.exists(os.path.join(self.model_dir, str(model_step)+'rec')):
#                 os.makedirs(os.path.join(self.model_dir, str(model_step)+'rec'))
        feed_dict = {self.X: imgs, self.lambda_zlogvar: lambda_zlogvar}
        rec_imgs, means_c, variance_c_var, covariance_c = self.sess.run(
            [self.G_dec2, self.means_c, self.variance_c_var, self.covariance_c], 
           feed_dict=feed_dict)
#         rec_imgs = self.sess.run(self.G_dec2, feed_dict=feed_dict)
        if DEBUG:
            # TODO:
            from my_utils import describe
            describe(imgs, 'LrLiVAE/rec_samples/imgs')
            describe(rec_imgs, 'LrLiVAE/rec_samples/rec_imgs')
#             describe(means_c, 'LrLiVAE/rec_samples/means_c')
#             describe(variance_c_var, 'LrLiVAE/rec_samples/variance_c_var')
#             describe(covariance_c, 'LrLiVAE/rec_samples/covariance_c')
        
        return rec_imgs
    
    def gen_samples(self, model_step, num_samples):
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step)))
        if not os.path.exists(os.path.join(self.model_dir, str(model_step))):
            os.makedirs(os.path.join(self.model_dir, str(model_step)))
        batch_size = 530
        sampleNo = 0
        for i in range(num_samples // batch_size):
            y_rand = np.tile(np.arange(0, self.y_dim), batch_size // self.y_dim)
            samples = self.sess.run(self.G_sample, feed_dict={self.z_c: sample_z(batch_size, self.zc_dim), self.z_p: sample_z(batch_size, self.z_dim), self.Y_rand: y_rand})
            if self.data.is_tanh:
                samples = (samples + 1) / 2
            for j, sample in enumerate(samples):
                sampleNo += 1
                sample_path = os.path.join(self.model_dir, str(model_step), str(y_rand[j]) + '_' + str(sampleNo) + '.jpg')
                skimage.io.imsave(sample_path, img_as_ubyte(sample))

    def vary_zs_across_c(self, model_step, batch_size=20):
        if not os.path.exists(os.path.join(self.model_dir, str(model_step) + '_varyzs')):
            os.makedirs(os.path.join(self.model_dir, str(model_step) + '_varyzs'))
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step)))
        z_p = np.random.normal(0, 1, size=[batch_size, 1, self.z_dim])
        z_c1 = np.zeros((1, self.z_dim))#sample_z(1, self.z_dim)
        z_c2 = np.zeros((1, self.z_dim))#sample_z(1, self.z_dim)
        z_c = np.concatenate([z_c1, z_c2], axis=0)
        y_rand = np.random.choice(self.y_dim, batch_size*2)
        z_sample_c = self.sess.run(self.z_sample_c, feed_dict={self.z_c:np.tile(z_c, (batch_size, 1)), self.Y_rand:y_rand})

        zcs = []
        for i in range(batch_size):
            z_c1 = z_sample_c[i*2]
            z_c2 = z_sample_c[i*2+1]
            for alpha in np.linspace(0, 1, 8):
                z_c_curr = alpha * z_c1 + (1-alpha) * z_c2
                zcs.append(z_c_curr)
        samples = self.sess.run(self.G_sample, feed_dict={self.z_sample_c: zcs, self.z_p: np.reshape(np.tile(z_p, (1, 8, 1)), (batch_size*8, -1))})
        if self.data.is_tanh:
            samples = (samples + 1) /2
        for i in range(batch_size):
            for j in range(8):
                sample_path = os.path.join(self.model_dir, str(model_step) + '_varyzs', str(i) + '_' + str(j)+ '.jpg')
                skimage.io.imsave(sample_path, img_as_ubyte(samples[8*i+j]))

    def vary_z(self, model_step, batch_size=24):
        if not os.path.exists(os.path.join(self.model_dir, str(model_step) + '_varyz')):
            os.makedirs(os.path.join(self.model_dir, str(model_step) + '_varyz'))
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step)))
        # z_p = np.random.normal(0, 1, size=[batch_size, 1, self.z_dim])
        # z_c1 = np.zeros((1, self.z_dim))
        # z_c2 = np.ones((1, self.z_dim))*3
        # zcs = []
        # for alpha in np.linspace(0, 1, 8):
        #     zc_curr = alpha * z_c2 + (1-alpha) * z_c1
        #     zcs.append(zc_curr)
        # zcs = np.array(zcs)
        # samples = self.sess.run(self.G_sample, feed_dict={self.z_c: np.reshape(np.tile(zcs, (batch_size, 1, 1)), (batch_size*8, self.z_dim)), self.z_p: np.reshape(np.tile(z_p, (1, 8, 1)),
        #                                                                        (batch_size * 8, -1)), self.Y_rand:np.reshape(np.tile(np.reshape(np.random.choice(self.y_dim, batch_size),(batch_size,1)),(1,8)), -1)})
        z_p = np.random.normal(0, 1, size=[batch_size, 1, self.z_dim])
        z_c1 = np.zeros((1, self.z_dim))
        z_c2 = np.ones((1, self.z_dim))*3
        zcs = []
        for alpha in np.linspace(0, 1, 8):
            zc_curr = alpha * z_c2 + (1-alpha) * z_c1
            zcs.append(zc_curr)
        zcs = np.array(zcs)
        samples = self.sess.run(self.G_sample, feed_dict={self.z_p: np.reshape(np.tile(zcs, (batch_size, 1, 1)), (batch_size*8, self.z_dim)), self.z_c: np.reshape(np.tile(z_p, (1, 8, 1)),
                                                                               (batch_size * 8, -1)), self.Y_rand:np.reshape(np.tile(np.reshape(np.random.choice(self.y_dim, batch_size),(batch_size,1)),(1,8)), -1)})

        if self.data.is_tanh:
            samples = (samples + 1) / 2
        for i in range(batch_size):
            for j in range(8):
                sample_path = os.path.join(self.model_dir, str(model_step) + '_varyz', 'zu_' + str(i) + '_' + str(j) + '.jpg')
                skimage.io.imsave(sample_path, img_as_ubyte(samples[8 * i + j]))


    def draw_zc_distribution(self, model_step, batch_size=100):
        # ckpt = tf.train.get_checkpoint_state(model_dir)
        print('Restoring from {}...'.format('model.ckpt-' + str(model_step)),
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step))))
        means, covariance = self.sess.run([self.means_c, self.covariance_c])
        zs = [[] for _ in range(min(self.y_dim, 10))]
        clsnum = [0 for _ in range(min(self.y_dim, 10))]
        # num_examples = self.data.data.train.num_examples
        num_examples = 20000
        for iter in range(num_examples // batch_size):
            X_b, Y_b = self.data(batch_size)
            z_b = self.sess.run(self.z_enc_c, feed_dict={self.X: X_b})
            for index, y in enumerate(Y_b):
                if y > 9 :continue
                zs[y].append(z_b[index])
                clsnum[y] += 1
        reshape_zs = []
        for i in range(min(self.y_dim, 10)):
            reshape_zs.extend(zs[i])
        reshape_zs = np.stack(reshape_zs)
        reshape_zs = np.vstack([reshape_zs, means])
        clsnum = np.cumsum(clsnum)
        z_embedded = TSNE(n_components=2).fit_transform(reshape_zs)
        fig = plt.figure()
        colors = ['red', 'green', 'purple', 'blue', 'yellow', 'pink', 'orange', 'brown', 'cyan', 'teal'] #np.random.rand(3,)
        for i in range(min(self.y_dim, 10)):
            if i == 0:
                cls_z_embedded = z_embedded[0: clsnum[0], :]
            else:
                cls_z_embedded = z_embedded[clsnum[i - 1]: clsnum[i], :]
            plt.scatter(cls_z_embedded[:, 0], cls_z_embedded[:, 1], c=colors[i], marker='o',linewidths=0.2)
            plt.scatter(z_embedded[clsnum[-1] + i, 0], z_embedded[clsnum[-1] + i, 1], c='black')
        plt.savefig(os.path.join(sample_folder, str(model_step) + 'zc.png'))
        plt.close(fig)

    def draw_zp_distribution(self, model_step, batch_size=100):
        # ckpt = tf.train.get_checkpoint_state(model_dir)
        print('Restoring from {}...'.format('model.ckpt-' + str(model_step)))
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step)))
        zs = [[] for _ in range(min(self.y_dim, 10))]
        clsnum = [0 for _ in range(min(self.y_dim, 10))]
        # num_examples = self.data.data.train.num_examples
        num_examples = 20000
        for iter in range(num_examples // batch_size):
            X_b, Y_b = self.data(batch_size)
            z_b = self.sess.run(self.z_enc_p, feed_dict={self.X: X_b})
            for index, y in enumerate(Y_b):
                if y > 9 :continue
                zs[y].append(z_b[index])
                clsnum[y] += 1
        reshape_zs = []
        for i in range(min(self.y_dim, 10)):
            reshape_zs.extend(zs[i])
        reshape_zs = np.stack(reshape_zs)
        clsnum = np.cumsum(clsnum)
        z_embedded = TSNE(n_components=2).fit_transform(reshape_zs)
        fig = plt.figure()
        colors = ['red', 'green', 'purple', 'blue', 'yellow', 'pink', 'orange', 'brown', 'cyan', 'teal'] #np.random.rand(3,)
        for i in range(min(self.y_dim, 10)):
            if i == 0:
                cls_z_embedded = z_embedded[0: clsnum[0], :]
            else:
                cls_z_embedded = z_embedded[clsnum[i - 1]: clsnum[i], :]
            plt.scatter(cls_z_embedded[:, 0], cls_z_embedded[:, 1], c=colors[i], marker='o',linewidths=0.2)
        plt.savefig(os.path.join(sample_folder, str(model_step) + 'zp.png'))
        plt.close(fig)

    def image_inpainting(self, model_step):
        bs = 20
        image, _ = self.data(bs)
        coord = np.random.choice(self.data.size - 20, 2)
        mask = np.ones((bs, self.data.size, self.data.size, self.data.channel))
        mask[:, coord[0]:coord[0]+20,coord[1]:coord[1]+20, :] = 0
        image_corp = image * mask
        print('Restoring from {}...'.format('model.ckpt-' + str(model_step)))
        self.saver.restore(self.sess, os.path.join(self.model_dir, 'model.ckpt-' + str(model_step)))
        gen_image = self.sess.run(self.G_dec, feed_dict={self.X: image_corp})
        inpaint_image = image * mask + gen_image * (1-mask)
        if self.data.is_tanh:
            image = (image + 1) / 2
            image_corp = (image_corp + 1) / 2
            inpaint_image = (inpaint_image + 1) /2
            gen_image = (gen_image + 1) /2
        fig = plt.figure(figsize = (3,bs))
        gs = gridspec.GridSpec(bs, 3)
        for i, sample in enumerate([image, image_corp, inpaint_image]):
            for j in range(bs):
                ax = plt.subplot(gs[i +j*3])
                plt.axis('off')
                ax.set_xticklabels([])
                ax.set_yticklabels([])
                ax.set_aspect('equal')
                plt.imshow(sample[j], cmap='Greys_r')
        plt.savefig(os.path.join(sample_folder, str(model_step) + '_inpainting.png'))
        plt.close(fig)

    def exchange_id_att(self, model_step):
        print('Restoring from {}...'.format('model.ckpt-' + str(model_step)))
        self.saver.restore(self.sess, os.path.join(self.model_dir,'model.ckpt-' + str(model_step)))
        if not os.path.exists(os.path.join(self.model_dir, str(model_step)+'_exc')):
            os.makedirs(os.path.join(self.model_dir, str(model_step)+'_exc'))
        bs = 40
        image, label = self.data(bs, random_flip = False)
        zcs = self.sess.run(self.z_enc_c, feed_dict={self.X: image[0::2]})
        zps = self.sess.run(self.z_enc_p, feed_dict={self.X: image[1::2]})
        syn_images=[(image[i]+1)/2 for i in range(1,bs,2)]
        samples = self.sess.run(self.G_dec, feed_dict={self.z_enc_c: np.reshape(np.tile(zcs, bs/2), (-1, self.zc_dim)), self.z_enc_p: np.tile(zps, (bs/2,1))})
        for j in range(len(zcs)):
            syn_images.append((image[j*2]+1)/2)
            syn_images.extend((samples[j * bs/2+i]+1)/2 for i in range(bs/2))
        # if self.data.is_tanh:
        #     syn_images = (syn_images + 1) / 2
#        fig = plt.figure(figsize=(30, 30))
#        gs = gridspec.GridSpec(21, 21)
#        for i, sample in enumerate(syn_images):
#            ax = plt.subplot(gs[i+1])
#            plt.axis('off')
#            ax.set_xticklabels([])
#            ax.set_yticklabels([])
#            ax.set_aspect('equal')
#            plt.imshow(syn_images[i], cmap='Greys_r')
#        plt.savefig(sample_folder + str(model_step) + '_syn.png', bbox_inches='tight')
#        plt.close(fig)
        for j, sample in enumerate(syn_images):
            col = (j + 1) % (bs/2 + 1)
            row = (j + 1) // (bs/2 + 1)
            sample_path = os.path.join(self.model_dir, str(model_step)+'_exc', str(row) + '_' + str(col) + '.jpg')
            skimage.io.imsave(sample_path, img_as_ubyte(sample))


def get_dataloader(args):
    
    return data


# TODO: get_subnets
# def get_subnets(args, data):
    
#     if args.dataset == 'facescrub':
# #         data = facescrub(is_tanh=True, size = img_size)
#         generator = GeneratorFace(size = data.size)
#         identity = IdentityFace(data.y_dim, data.z_dim, size = data.size)
#         attribute = AttributeFace(data.z_dim, size = data.size)
#         discriminator = DiscriminatorFaceSN(size=data.size)
#         latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
        
#     elif args.dataset == 'mnist':
# #         data = mnist(is_tanh=True)
#         generator = GeneratorMnist(size = data.size)
# #         identity = IdentityMnist(data.y_dim, data.z_dim, size = data.size) # z_dim should be data.zc_dim ??
#         identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size) # z_dim should be data.zc_dim ??
#         attribute = AttributeMnist(data.z_dim, size = data.size)
#         discriminator = DiscriminatorMnistSN(size=data.size)
# #         discriminator = DiscriminatorMnistSNComb(size=data.size) # which to use?
#         latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
    
#     elif 'omniglot' in args.dataset:
# #         datapath = os.path.join(closer_look_path, 'filelists/omniglot/hdf5')
# #         split = 'noLatin' if 'noLatin' in args.dataset else 'train'
# #         data = Omniglot(datapath=datapath, size=args.img_size, batch_size=batch_size, 
# #                        is_tanh=True, flag='conv', split=split) # train, noLatin
#         generator = GeneratorMnist(size = data.size)
# #         identity = IdentityMnist(data.y_dim, data.z_dim, size = data.size) # z_dim should be data.zc_dim ??
#         identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size) # z_dim should be data.zc_dim ??
#         attribute = AttributeMnist(data.z_dim, size = data.size)
#         discriminator = DiscriminatorMnistSN(size=data.size)
# #         discriminator = DiscriminatorMnistSNComb(size=data.size) # which to use?
#         latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
    
#     elif args.dataset == 'miniImagenet': # TODO: design the net structure
# #         data = MiniImagenet(datapath='../../meta_few-shot/CloserLookFewShot/filelists/miniImagenet', size=args.img_size)
# #         data_path = os.path.join(closer_look_path, 'filelists/miniImagenet/hdf5')
# #         data = MiniImagenetV3(datapath=data_path, 
# #                               size=args.img_size, batch_size=batch_size, aug=True) # TODO: aug
# #         generator = GeneratorMnist(size = data.size)
#         generator = GeneratorMiniImg(size = data.size)
# #         identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size)
#         identity = IdentityFace(data.y_dim, data.zc_dim, size = data.size)
# #         attribute = AttributeMnist(data.z_dim, size = data.size)
#         attribute = AttributeFace(data.z_dim, size = data.size)
# #         discriminator = DiscriminatorMnistSN(size=data.size)
#         discriminator = DiscriminatorFaceSN(size=data.size)
#         latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
    
#     return generator, identity, attribute, discriminator, latent_discriminator


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', type=str, default='0',
                        help='Specify which gpu to use by `CUDA_VISIBLE_DEVICES=num python train.py **kwargs`\
                              or `python train.py --gpu num` if you\'re running on a multi-gpu enviroment.\
                              You need to do nothing if your\'re running on a single-gpu environment or\
                              the gpu is assigned by a resource manager program.')
    parser.add_argument('--img_size', type=int, default=None, help='input image size')
    parser.add_argument('--experiment_name', default='facescrub-64')
    parser.add_argument('--batch_size', type=int, default=96)
    parser.add_argument('--mode', default='training', choices=['training', 'generation', 'inpainting', 'exchanging'])
    # add dataset choice
    parser.add_argument('--dataset', default='facescrub', choices=['facescrub', 'mnist', 'miniImagenet', 'omniglot', 'omniglot-noLatin'])
    parser.add_argument('--stop_iter', default=None, type=int, help='how many iterations to stop. (only for mode=training)')
    parser.add_argument('--restore', action='store_true', help='whether load model or not when training.')
    
    parser.add_argument('--do_eval', action='store_true', 
                        help='when training, whether evaluate the network performance with is_training=False.')
    args = parser.parse_args()

    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    
    img_size_dict = {'facescrub':64, 'mnist':28, 'miniImagenet':84, 'omniglot':28, 'omniglot-noLatin':28}
    if args.img_size is None:
        args.img_size = img_size_dict[args.dataset]
    img_size = args.img_size
    experiment_name = args.experiment_name
    batch_size = args.batch_size
    mode = args.mode

    sample_folder = os.path.join('Samples',experiment_name)
    if not os.path.exists(sample_folder):
        os.makedirs(sample_folder)

    if args.dataset == 'facescrub':
        data = facescrub(is_tanh=True, size = img_size)
        generator = GeneratorFace(size = data.size)
        identity = IdentityFace(data.y_dim, data.z_dim, size = data.size)
        attribute = AttributeFace(data.z_dim, size = data.size)
        discriminator = DiscriminatorFaceSN(size=data.size)
        latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
        
    elif args.dataset == 'mnist':
        data = mnist(is_tanh=True)
        generator = GeneratorMnist(size = data.size)
#         identity = IdentityMnist(data.y_dim, data.z_dim, size = data.size) # z_dim should be data.zc_dim ??
        identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size) # z_dim should be data.zc_dim ??
        attribute = AttributeMnist(data.z_dim, size = data.size)
        discriminator = DiscriminatorMnistSN(size=data.size)
#         discriminator = DiscriminatorMnistSNComb(size=data.size) # which to use?
        latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
    
    elif 'omniglot' in args.dataset:
        datapath = os.path.join(closer_look_path, 'filelists/omniglot/hdf5')
        split = 'noLatin' if 'noLatin' in args.dataset else 'train'
        data = Omniglot(datapath=datapath, size=args.img_size, batch_size=batch_size, 
                       is_tanh=True, flag='conv', split=split) # train, noLatin
        generator = GeneratorMnist(size = data.size)
#         identity = IdentityMnist(data.y_dim, data.z_dim, size = data.size) # z_dim should be data.zc_dim ??
        identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size) # z_dim should be data.zc_dim ??
        attribute = AttributeMnist(data.z_dim, size = data.size)
        discriminator = DiscriminatorMnistSN(size=data.size)
#         discriminator = DiscriminatorMnistSNComb(size=data.size) # which to use?
        latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)
    
    elif args.dataset == 'miniImagenet': # TODO: design the net structure
#         data = MiniImagenet(datapath='../../meta_few-shot/CloserLookFewShot/filelists/miniImagenet', size=args.img_size)
        data_path = os.path.join(closer_look_path, 'filelists/miniImagenet/hdf5')
        data = MiniImagenetV3(datapath=data_path, 
                              size=args.img_size, batch_size=batch_size, aug=True) # TODO: aug
#         generator = GeneratorMnist(size = data.size)
        generator = GeneratorMiniImg(size = data.size)
#         identity = IdentityMnist(data.y_dim, data.zc_dim, size = data.size)
        identity = IdentityFace(data.y_dim, data.zc_dim, size = data.size)
#         attribute = AttributeMnist(data.z_dim, size = data.size)
        attribute = AttributeFace(data.z_dim, size = data.size)
#         discriminator = DiscriminatorMnistSN(size=data.size)
        discriminator = DiscriminatorFaceSN(size=data.size)
        latent_discriminator = LatentDiscriminator(y_dim = data.y_dim)


    # TODO: modify is_training & wgan conditioned on mode
    is_training = True
    # run

    wgan = GMM_AE_GAN(generator, identity, attribute, discriminator, latent_discriminator, data, is_training,
                      log_dir=os.path.join('logs', experiment_name),
                      model_dir=os.path.join('models',experiment_name))
    if mode == 'training':
        if args.stop_iter == None:
            training_iters = {'mnist':10001, 'facescrub':52001, 'miniImagenet':300001, 'omniglot':20001, 'omniglot-noLatin':10001}
            args.stop_iter = training_iters[args.dataset]
        
        if args.do_eval:
#             wgan_eval = GMM_AE_GAN(generator, identity, attribute, discriminator, latent_discriminator, data, 
#                                is_training=False,
#                               log_dir=os.path.join('logs', experiment_name),
#                               model_dir=os.path.join('models',experiment_name))
            wgan_eval = True
        else:
            wgan_eval = None
        wgan.train(sample_folder, training_iters=args.stop_iter, batch_size = batch_size, restore = args.restore, 
                  eval_model=wgan_eval)
    # wgan.draw_zp_distribution(249000)
    elif mode == 'generation':
        model_step = {'mnist':10000, 'facescrub':52000, 'miniImagenet':300000, 'omniglot':20000, 'omniglot-noLatin':10000}
        num_samples = {'mnist':530, 'facescrub':53000, 'miniImagenet':530, 'omniglot':530, 'omniglot-noLatin':530}
        wgan.gen_samples(model_step=model_step[args.dataset], num_samples=num_samples[args.dataset])
    elif mode == 'inpainting':
        if args.dataset == 'facescrub':
            wgan.image_inpainting(52000)
        else:
            print('code unfinished!!!!!!')
    # wgan.vary_zs_across_c(52000)
    # wgan.vary_z(52000)
    elif mode == 'exchanging':
        wgan.exchange_id_att(52000)
