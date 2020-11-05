# Neural Style Transfer CLI

This code base serves as a CLI for the application of [Neural Style Transfer](https://www.tensorflow.org/tutorials/generative/style_transfer). 
In short, Neural Style Transfer transforms an original image based on the style of a second image. See the example below.

Implementation was based on the [Neural Style Transfer paper by Gatys Et Al 2015](https://arxiv.org/abs/1508.06576).
<br>
Inspiration and a significant chunk of code was obtained by [Raymond Yuan](https://github.com/tensorflow/models/tree/master/research/nst_blogpost).

## Example

####Using this as the original image
![alt text](https://github.com/dimitrisnikolaou10/Neural-Style-Transfer/blob/main/lib/input/content/plagiari.jpg)

####And "stealing" the style from Van Gogh's Starry Night
![alt text](https://github.com/dimitrisnikolaou10/Neural-Style-Transfer/blob/main/lib/input/style/Van_Gogh-Starry_Night.jpg)

####We get this as an outcome.
![alt text](https://github.com/dimitrisnikolaou10/Neural-Style-Transfer/blob/main/lib/output/plagiari_Van_Gogh-Starry_Night_output.jpg 
)

####Cool right? Try it yourself.


## Instructions
<ol>
<li>Clone repo locally
<li>Within the source folder run main.py the following way:
</ol>
<pre><code>python main.py --original [PATH_TO_ORIGINAL] --style [PATH_TO_STYLE]
</code></pre>

## Further Development
Not much more you can do here to be honest, but feel free to push more images of your favorite artists in the style folder.
