import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams['figure.figsize'] = (10,10)
mpl.rcParams['axes.grid'] = False

import numpy as np
from PIL import Image
import time
import functools
import argparse

""" If you run this locally make sure your SSL verificatiton is set the way you want to """
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

# %tensorflow_version 1.x
import tensorflow as tf

from tensorflow.python.keras.preprocessing import image as kp_image
from tensorflow.python.keras import models
from tensorflow.python.keras import losses
from tensorflow.python.keras import layers
from tensorflow.python.keras import backend as K

""" SET SOME CONSTANTS """

# Content layer where will pull our feature maps
CONTENT_LAYERS = ['block5_conv2']

# Style layer we are interested in
STYLE_LAYERS = ['block1_conv1',
                'block2_conv1',
                'block3_conv1',
                'block4_conv1',
                'block5_conv1'
               ]

NUM_CONTENT_LAYERS = len(CONTENT_LAYERS)
NUM_STYLE_LAYERS = len(STYLE_LAYERS)

# tf.enable_eager_execution() NO NEED FOR TF > 2.0 to run tf.enable_eager_execution()
# print("Eager execution: {}".format(tf.executing_eagerly()))

# Set up some global values here
CONTENT_PATH = '../lib/input/content/plagiari.jpg'
STYLE_PATH = '../lib/input/style/Van_Gogh-Starry_Night.jpg'


def load_img(path_to_img):
    max_dim = 512
    img = Image.open(path_to_img)
    long = max(img.size)
    scale = max_dim / long
    img = img.resize((round(img.size[0] * scale), round(img.size[1] * scale)), Image.ANTIALIAS)

    img = kp_image.img_to_array(img)

    # We need to broadcast the image array such that it has a batch dimension
    img = np.expand_dims(img, axis=0)
    return img


def imshow(img, title=None):
    # Remove the batch dimension
    out = np.squeeze(img, axis=0)
    # Normalize for display
    out = out.astype('uint8')
    plt.imshow(out)
    if title is not None:
        plt.title(title)
    plt.imshow(out)


def load_and_process_img(path_to_img):
    img = load_img(path_to_img)
    img = tf.keras.applications.vgg19.preprocess_input(img)
    return img


def deprocess_img(processed_img):
    x = processed_img.copy()
    if len(x.shape) == 4:
        x = np.squeeze(x, 0)
    assert len(x.shape) == 3, ("Input to deprocess image must be an image of "
                             "dimension [1, height, width, channel] or [height, width, channel]")
    if len(x.shape) != 3:
        raise ValueError("Invalid input to deprocessing image")

    # perform the inverse of the preprocessing step
    x[:, :, 0] += 103.939
    x[:, :, 1] += 116.779
    x[:, :, 2] += 123.68
    x = x[:, :, ::-1]

    x = np.clip(x, 0, 255).astype('uint8')
    return x


def get_model():
    """ Creates our model with access to intermediate layers.

    This function will load the VGG19 model and access the intermediate layers.
    These layers will then be used to create a new model that will take input image
    and return the outputs from these intermediate layers from the VGG model.

    Returns:
    returns a keras model that takes image inputs and outputs the style and
    content intermediate layers.
    """
    # Load our model. We load pretrained VGG, trained on imagenet data
    vgg = tf.keras.applications.vgg19.VGG19(include_top=False, weights='imagenet')
    vgg.trainable = False
    # Get output layers corresponding to style and content layers
    style_outputs = [vgg.get_layer(name).output for name in STYLE_LAYERS]
    content_outputs = [vgg.get_layer(name).output for name in CONTENT_LAYERS]
    model_outputs = style_outputs + content_outputs
    # Build model
    return models.Model(vgg.input, model_outputs)


def get_content_loss(base_content, target):
    return tf.reduce_mean(tf.square(base_content - target))


def gram_matrix(input_tensor):
    # We make the image channels first
    channels = int(input_tensor.shape[-1])
    a = tf.reshape(input_tensor, [-1, channels])
    n = tf.shape(a)[0]
    gram = tf.matmul(a, a, transpose_a=True)
    return gram / tf.cast(n, tf.float32)


def get_style_loss(base_style, gram_target):
    """Expects two images of dimension h, w, c"""
    # height, width, num filters of each layer
    # We scale the loss at a given layer by the size of the feature map and the number of filters
    height, width, channels = base_style.get_shape().as_list()
    gram_style = gram_matrix(base_style)

    return tf.reduce_mean(tf.square(gram_style - gram_target))# / (4. * (channels ** 2) * (width * height) ** 2)


def get_feature_representations(model, content_path, style_path):
    """Helper function to compute our content and style feature representations.

    This function will simply load and preprocess both the content and style
    images from their path. Then it will feed them through the network to obtain
    the outputs of the intermediate layers.

    Arguments:
    model: The model that we are using.
    content_path: The path to the content image.
    style_path: The path to the style image

    Returns:
    returns the style features and the content features.
    """
    # Load our images in
    content_image = load_and_process_img(content_path)
    style_image = load_and_process_img(style_path)

    # batch compute content and style features
    style_outputs = model(style_image)
    content_outputs = model(content_image)

    # Get the style and content feature representations from our model
    style_features = [style_layer[0] for style_layer in style_outputs[:NUM_STYLE_LAYERS]]
    content_features = [content_layer[0] for content_layer in content_outputs[NUM_STYLE_LAYERS:]]
    return style_features, content_features


def compute_loss(model, loss_weights, init_image, gram_style_features, content_features):
    """This function will compute the loss total loss.

    Arguments:
    model: The model that will give us access to the intermediate layers
    loss_weights: The weights of each contribution of each loss function.
      (style weight, content weight, and total variation weight)
    init_image: Our initial base image. This image is what we are updating with
      our optimization process. We apply the gradients wrt the loss we are
      calculating to this image.
    gram_style_features: Precomputed gram matrices corresponding to the
      defined style layers of interest.
    content_features: Precomputed outputs from defined content layers of
      interest.

    Returns:
    returns the total loss, style loss, content loss, and total variational loss
    """
    style_weight, content_weight = loss_weights

    # Feed our init image through our model. This will give us the content and
    # style representations at our desired layers. Since we're using eager
    # our model is callable just like any other function!
    model_outputs = model(init_image)

    style_output_features = model_outputs[:NUM_STYLE_LAYERS]
    content_output_features = model_outputs[NUM_STYLE_LAYERS:]

    style_score = 0
    content_score = 0

    # Accumulate style losses from all layers
    # Here, we equally weight each contribution of each loss layer
    weight_per_style_layer = 1.0 / float(NUM_STYLE_LAYERS)
    for target_style, comb_style in zip(gram_style_features, style_output_features):
        style_score += weight_per_style_layer * get_style_loss(comb_style[0], target_style)

    # Accumulate content losses from all layers
    weight_per_content_layer = 1.0 / float(NUM_CONTENT_LAYERS)
    for target_content, comb_content in zip(content_features, content_output_features):
        content_score += weight_per_content_layer* get_content_loss(comb_content[0], target_content)

    style_score *= style_weight
    content_score *= content_weight

    # Get total loss
    loss = style_score + content_score
    return loss, style_score, content_score


def compute_grads(cfg):
    with tf.GradientTape() as tape:
        all_loss = compute_loss(**cfg)
    # Compute gradients wrt input image
    total_loss = all_loss[0]
    return tape.gradient(total_loss, cfg['init_image']), all_loss


def run_style_transfer(content_path,
                       style_path,
                       num_iterations=1000,
                       content_weight=1e3,
                       style_weight=1e-2):
    # We don't need to (or want to) train any layers of our model, so we set their
    # trainable to false.
    model = get_model()
    for layer in model.layers:
        layer.trainable = False

    # Get the style and content feature representations (from our specified intermediate layers)
    style_features, content_features = get_feature_representations(model, content_path, style_path)
    gram_style_features = [gram_matrix(style_feature) for style_feature in style_features]

    # Set initial image
    init_image = load_and_process_img(content_path)
    init_image = tf.Variable(init_image, dtype=tf.float32)
    # Create our optimizer
    opt = tf.keras.optimizers.Adam(learning_rate=5, beta_1=0.99, epsilon=1e-1)
    # opt = tf.train.AdamOptimizer()

    # For displaying intermediate images
    iter_count = 1

    # Store our best result
    best_loss, best_img = float('inf'), None

    # Create a nice config
    loss_weights = (style_weight, content_weight)
    cfg = {
        'model': model,
        'loss_weights': loss_weights,
        'init_image': init_image,
        'gram_style_features': gram_style_features,
        'content_features': content_features
    }

    # For displaying
    num_rows = 2
    num_cols = 5
    display_interval = num_iterations / (num_rows * num_cols)
    start_time = time.time()
    global_start = time.time()

    norm_means = np.array([103.939, 116.779, 123.68])
    min_vals = -norm_means
    max_vals = 255 - norm_means

    imgs = []
    for i in range(num_iterations):

        grads, all_loss = compute_grads(cfg)
        loss, style_score, content_score = all_loss
        opt.apply_gradients([(grads, init_image)])
        clipped = tf.clip_by_value(init_image, min_vals, max_vals)
        init_image.assign(clipped)
        end_time = time.time()

        # small script to track progress
        step = round((i+1)/num_iterations * 100, 2)
        print("We are at {}%.".format(step))


    if loss < best_loss:
        # Update best loss and best image from total loss.
        best_loss = loss
        best_img = deprocess_img(init_image.numpy())

    if i % display_interval == 0:
        start_time = time.time()

        # Use the .numpy() method to get the concrete numpy array
        plot_img = init_image.numpy()
        plot_img = deprocess_img(plot_img)
        imgs.append(plot_img)
        # IPython.display.clear_output(wait=True)
        # IPython.display.display_png(Image.fromarray(plot_img))
        print('Iteration: {}'.format(i))
        print('Total loss: {:.4e}, '
              'style loss: {:.4e}, '
              'content loss: {:.4e}, '
              'time: {:.4f}s'.format(loss, style_score, content_score, time.time() - start_time))
    print('Total time: {:.4f}s'.format(time.time() - global_start))
    # IPython.display.clear_output(wait=True)
    plt.figure(figsize=(14, 4))
    for i, img in enumerate(imgs):
        plt.subplot(num_rows, num_cols, i + 1)
        plt.imshow(img)
        plt.xticks([])
        plt.yticks([])

    return best_img, best_loss


def show_results(best_img, content_path, style_path, show_large_final=True):
    plt.figure(figsize=(10, 5))
    content = load_img(content_path)
    style = load_img(style_path)

    plt.subplot(1, 2, 1)
    imshow(content, 'Content Image')

    plt.subplot(1, 2, 2)
    imshow(style, 'Style Image')

    if show_large_final:
        plt.figure(figsize=(10, 10))

        plt.imshow(best_img)
        plt.title('Output Image')
        plt.show()


def main(content_path, style_path):
    best, best_loss = run_style_transfer(content_path,
                                         style_path, num_iterations=50)

    im = Image.fromarray(best)
    content_name = content_path.split("/")[-1].split(".")[0]
    style_name = style_path.split("/")[-1].split(".")[0]
    im.save("../lib/output/" + content_name + "_" + style_name + "_output.jpg", "JPEG")

    show_results(best, content_path, style_path)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    '''
    Command line options
    '''
    parser.add_argument(
        '--original', type=str,
        help='path to model weight file, default ' + CONTENT_PATH
    )

    parser.add_argument(
        '--style', type=str,
        help='path to anchor definitions, default ' + STYLE_PATH
    )

    arguments = parser.parse_args()

    try:
        content_path = arguments.original
    except:
        content_path = CONTENT_PATH

    try:
        style_path = arguments.style
    except:
        style_path = STYLE_PATH

    main(content_path, style_path)
