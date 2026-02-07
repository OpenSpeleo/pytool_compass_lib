# Depth Gauge

If you are surveying sumps and underwater caves, you have the option of entering
depth gauge data instead of inclination angle. Cave divers generally use a scuba
diver's water depth gauge in place of the inclinometer when surveying an
underwater cave. The depth gauge measures the depth of the instrument under the
surface of the water. Depth gauge measurements are enabled by selecting the "W"
(Water Depth) option in the inclination section of the Survey Format menu.
Because of the fact that depth gauge measurements don't make logical sense with
redundant backsights, both options cannot be turned on at the same time.

**Depth Gauge Issues:** A diver’s depth gauge instrument measures the total
depth of the instrument below the surface of the water. However, Compass cannot
use this measurement alone. In a normal survey shot, inclination shows the slope
of the shot. In a depth gauge shot, you have to have the depth of both the From
and To station before you can calculate the inclination angle of the shot. For
this reason, normal survey shots and depth gauge shots are not equivalent.

This would not be a problem if you only had depth gauge shots, but in many
instances, you will have a mixture of depth gauge and normal shots. This causes
many problems. For example, you can have water filled caves that start at sea
level; in which case, the depth gauge values would always represent the depth
below sea level. On the other hand, you can have a sump that is thousands of
meters of above sea level and thousands of meters above the entrance. Thus,
you’d always have to know the starting elevation of the underwater survey. If a
depth gauge survey crosses surveys, the situation becomes even more complicated,
because the depth of the From station could be in a different survey or file.

**Entering Depth Gauge Measurements:** As a result of these issues, Compass
requires that depth gauge information be entered as the difference between the
From and To depths. For this reason, you must enter the difference between the
"From" and "To" station. In other words, you have to subtract the "To" station
depth from the "From" station depth (F-T). Remember, negative depth gauges mean
that you are going deeper, positive depth gauges mean you are going up.

**Validating Depth Gauge:** Depth gauge is a unique measurement because of the
geometry of the situation. Depth gauge measurements are limited by the shot's
length. In other words, a shot cannot go down any further than the length of the
shot. For this reason, the program checks for data where the depth is greater
than the shot length. If you try to enter a depth that is longer than the shot
or a shot that is shorter than the depth, the program will tell you that there
has been an error. Depending on the circumstance, the program will try to make
sense out of the error by adjusting either the shot length or the depth.

**Depth Gauge Sequence:** Because of the way depth gauge works, shot entry
sequence becomes important. If you have the program set so depth gauge is
entered before shot length, the depth gauge will be non-zero before the length
is set. This means that on nearly every shot, you get an error. This is not a
big problem since the program simply changes the length to match the depth.
Still, it is probably better to enter shot length before depth gauge.

**Depth Units:** Depth Gauge measurements can be entered in the any of the
standard units of length. Depth gauge uses whatever settings are being used by
the length measurements.
