# Neural Style Transfer CLI

This code base serves as a CLI for the application of [Neural Style Transfer](https://www.tensorflow.org/tutorials/generative/style_transfer). 
In short, Neural Style Transfer transforms an original image based on the style of a second image. See the example below.

<br>
Implementation was based on the [Neural Style Transfer paper by Gatys Et Al 2015](https://www.arxiv.org/abs/1508.06576).
<br>
Inspiration and a significant chunk of code was obtained by [Raymond Yuan](https://github.com/tensorflow/models/tree/master/research/nst_blogpost).

## Instructions
<ol>
<li>Clone repo locally
<li>Within the source folder run main.py the following way:
</ol>
<pre><code>python main.py --original [PATH_TO_ORIGINAL] --style [PATH_TO_STYLE]
</code></pre>

## Further Development
Not much more you can do here to be honest, but feel free to push more images of your favorite artists in the style folder.
