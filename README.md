This is a quick and dirty joystick diagram generator, for processing Joystick Gremlin files.

It's inspired by Joystick Diagrams, but JD is both too complex for my needs and did not fit my use case of mixed devices.

All this does is read a joystick diagram config, look for description strings, and uses those strings to map text into a template svg.

So if in your SVG you have text:
B1
or 
B1_S (for some modified key)

and in a the joystick diagram description field for button 1 you have:
B1|Fire Cannon|B1_S|

Then "B1" in the template will be replaced with "Fire Cannon" and "B1_S" will be replaced with ""

Basically this allows you to define the text you want on your template in Joystick Gremlin. It's not smart, but once 
set up it's easy to use. 

Usage 
python.exe .\diagram_generator.py <your_gremlin_file.xml> <your_template_file.svg>

The output will be named after your gremlin file (e.g. `<your_gremlin_file>.svg`).

Sample templates and outputs here:

### Template
![Template SVG](template.svg)

### Joystick Gremlin Setup
![Joystick Gremlin Setup](JG%20Screenshot.png)

### Example Output
![Example Output SVG](DCS%20KA-50.svg)
