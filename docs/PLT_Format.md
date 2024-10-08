# Plot Data Format: PLT

Ordinary COMPASS users never need to know anything about the content of
Plot Files; however, occasionally, it is useful to manipulate them with
other programs. For example, a programmer might want to read data from a
plot file or create specialized versions of plot files. For this reason,
the following section describes the COMPASS plot files in detail.

**Plot Files.** *Plot Files* are different from *Survey Data Files.
Survey Data Files* contain the original compass, tape and inclination
measurements that were gathered when the cave was surveyed. These type
of measurement are called polar coordinates. Unfortunately, most
printers and video cards require Cartesian coordinates to operate. For
this reason, one of the jobs of the Project Manager is to convert survey
data to Cartesian Coordinates. These Cartesian Coordinates are stored in
"Plot Files." Plot Files generally have the file extension of "PLT".

**ASCII Format.** COMPASS plot files are ordinary ASCII files that
contain no binary data. The only control character that will in the data
is a Control-Z, which is used as an End-Of-File character. Plot files
can contain extended ASCII characters above 128 or 7F hex. However, be
aware that there is more than one definition of the extended characters
and how they are displayed will depend on the font you are using. 
Generally speaking, plot files can be viewed and manipulated with simple
text editors.

**Units.** All coordinate data in the Plot File is specified in feet. It
is the responsibility of the program reading the data to convert data to
other units for display purposes. This also applies to the coordinates
of a Features, although the numerical values associated with the Feature
can be any conceivable unit.

**Types of Information.** Plot files contain two basic kinds of
information: Vector Information and Feature Information. Vector
Information is data that tells the computer how to draw lines that
describe the cave. Feature Information contains the locations,
magnitudes and routes associated with cave features. Cave features can
be almost anything that you might want to study in a cave. For example,
features could be formations, minerals, water, GIS information,
scientific data, etc.

**Commands.** The plot file consists of a series of commands that tell
the program to perform some specific action. Commands are line oriented.
The first character on each line is treated as a command. In some
instances, other letters on the same line indicate optional parameters
or subcommands. Arguments to the command appear on the rest of the line.
Most arguments are separated by space characters. Here is a list of
commands:

1. `N<survey name> D <month> <day> <year> C<comment>`. This command indicates
the start of a new survey. All commands that follow will be considered part
of that survey until another survey or feature is encountered.

   1. **Survey Name.** The "N" command character is immediately followed by
an ASCII text string containing the survey name. The survey name can be
a maximum of 12 characters long. The survey name cannot have spaces or
control characters in it, although it can have extended ASCII
characters.
 
   2. **Survey Date.** An optional survey date follows the survey name. The
survey date is proceeded by the letter "D" and it is written
numerically as Month, Day and Year. The Year is expected to be the full
year like 1994 not 94. Where the date is missing, COMPASS will
substitute a date of 1/1/1. However, it is better to include a date with
at least a valid year value. Otherwise, the Viewer will not have enough
colors to distinguish individual years in the "Complex Display" modes.

   3. **Survey Comment.** An optional survey comment follows the survey
date. Because of the way the data is parsed, the date field must be
present for the comment field to be read. The comment be up to 80
characters in length and can include any characters except Carriage
Return or Line Feed. 

2. `F<survey name>.` The `F` command has a similar format as the
`N` command. The `F` command identifies the start of a feature
survey. An ASCII text string containing the name of the feature item
immediately follows the letter `F`. The Feature Name can be a maximum
of 12 characters long. The name cannot have spaces or control characters
in it, although it can have extended ASCII characters.
 
The "R" command may optionally follow the feature name. It indicates
that numerical values will be associated with the feature data. The
command is followed by two floating-point numbers that specify the range
of values that will be encountered in the feature data. Programs use the
range of values to scale their response to individual feature values.
 
3. **D,M.** These commands begin a shot vector data record. The
following fields are contained within the record:
 
   1. **Plot Command.** Consisting of: Upper case `D` or `M`. `D`
indicates that the program should draw a line from the last location to
the location specified by the Cartesian point that follows. `M`
indicates that the program should move to the specified location without
drawing a line. An `M` must be the first command in the file and must
be the first command of any line sequence. However, there is no
requirement that each survey begin with an `M` command. In other words,
a single line sequence can cross several surveys without an `M`
command.
 
   2. **Cartesian Coordinates.** This item defines a location using three
floating-point numbers that specify the North, East and Vertical
distance from the origin of the cave. These values are always in feet.
 
   3. **Station Label Command.** This command is specified by the letter
`S`, followed by up to 12 characters of the station label. The name
cannot have spaces or control characters in it, although it can have
extended ASCII characters. There is no separator between the `S` and the
station label.
 
   4. **Passage Dimension Command.** This command is specified by the
letter `P` followed by four floating-point numbers specifying the
left, up, down and right distances from the station to the passage
walls. Each value is separated by spaces and all values are in feet. The
`P` command and following measurements are optional, and can be
omitted without preventing the file from working.
 
Values less than zero are considered to be missing or "Passage." The
left and right values are treated as measurements at a right angle to
the survey shot. Up and down values are treated as measurement in the
vertical direction. (Note. Displaying passage models of vertical or near
shots is a problem. Because of the fact that there is no consistent
standard for these types of shots, COMPASS may change the way it
interprets in the future.)
 
   5. **Distance From Entrance.** This command is specified by the letter
`I` followed by one floating-number specifying the distance between the
specified station and the entrance of the cave.

4. `L` The format of the `L` command is identical to the "D" and
`M` command except that it indicates the location of a feature rather
than the start or end of a vector. Programs use this command to place a
symbol, label or numerical values at certain locations on the map to
identify a cave feature. 

The optional `V` command follows the `P` command. It is used to
specify the value associated with a particular feature item. For
example, if a water sample showed 5 parts-per-million contamination, the
value of the item might be 5 or 5E-6. The number is usually specified in
scientific notation format. For example: 1.2345E-6. This ensures that a
broad range of numbers can be handled.

5. `Z<N min><N max><E min><E max><V min><V max>[I D]`. This command lists
the minimum and maximum dimensions of the cave being processed. Normally,
this command is the first command in the plot file. It allows the program
to scale the plot automatically without scanning through the whole cave.
The values are specified in feet and each parameter is separated by a space
character. The last item is optional. It begins with the letter `I` and is
followed by a floatingpoint number containing the distance from the entrance
of the most distant station in the cave.

6. `X<N min><N max><E min><E max><V min><V max>`. This
command follows each survey in the file, and lists the minimum and
maximum dimensions of that survey. This greatly speeds redrawing the
cave when changing scale, by allowing the program to tell if the survey
will be visible on the screen. The values are specified in feet and each
parameter is separated by a space character.

7. `S<section name>`. This command signifies the beginning of a new
section in the cave. Normally, this would mark the beginning of new
file, so normally the section name would derived from the file name. It
is used by programs to color, highlight or exclude particular parts of
the cave. The `S` command character is immediately followed by an ASCII
text string containing the survey name. The survey name can be a maximum
of 20 characters long. The name cannot have control characters in it,
although it can have spaces and extended ASCII characters. 
Here is a sample plot file: 

```
Z    -129.26    319.44    -94.30    439.00   -130.05    126.30  I 1357.3SFULFORD CAVENZ+ D 6 29 1994 CStream PassageM   123.5   -70.2   -87.1  SZ6  P    1.5    1.0    0.5    0.5  I    0.0  D   128.2   -65.9   -86.8  SZ7  P    0.0    3.0    1.0    3.0  I   21.8D   131.1   -65.4   -85.3  SZ8  P    3.5    2.0    5.0    1.0  I   45.5D   138.2   -63.3   -82.5  SZ9  P    0.0    0.0    0.0    0.0  I   58.9M   123.5   -70.2   -87.1  SZ6  P    1.5    1.0    0.5    0.5  I   72.8D   118.8   -79.1   -92.5  SZ10  P    1.5    1.0    2.5    3.0  I  105.8D   122.0   -75.8   -95.4  SZ11  P    2.5    0.5    2.5    1.5  I  126.8D   129.8   -79.1  -101.7  SZ12  P    0.5    4.0    0.5    1.5  I  105.8D   134.4   -82.9  -101.9  SZ13  P    0.0    0.0    0.0    0.0  I  138.6X     118.78    138.22    -82.94    -63.34   -101.90    -82.53FINSECTSL     0.0     0.0     0.0  SA1 P -9.0 -9.0 -9.0 -9.0L     8.6    17.2   -10.2  SA2 P -9.0 -9.0 -9.0 -9.0L    30.5    23.3   -17.2  SA3 P -9.0 -9.0 -9.0 -9.0L    37.5    12.4   -20.3  SA4 P -9.0 -9.0 -9.0 -9.0X       0.00     37.50      0.00     23.30    -20.30      0.00FWATER R 5.51234E2  8.12341E2L     0.0     0.0     0.0  SA1 P -9.0 -9.0 -9.0 -9.0 V 5.51234E2L     8.6    17.2   -10.2  SA2 P -9.0 -9.0 -9.0 -9.0 V 8.12341E2L    30.5    23.3   -17.2  SA3 P -9.0 -9.0 -9.0 -9.0 V 7.82543E2L    37.5    12.4   -20.3  SA4 P -9.0 -9.0 -9.0 -9.0X    0.00     37.50      0.00     23.30    -20.30      0.00 
```

The spacing of the elements in the file is not critical, provided that
at least one white space separates each item. However, the file must be
saved in ASCII text format, with a carriage return/line feed ending each
line. Omitting the spaces or carriage return/line feed will cause errors
when the file is used. 

8. `O<Datum>`. This command indicates that the following string will
be a description of the "Datum" used to convert between Longitude and
Latitude and UTM. For example, the current Datum used for most
topographical maps these days "North American 1983".

9. `G<UTM Zone>`. This command contains the UTM Zone for the cave.
If the value is zero or if the tag is missing, it indicates that no zone
was set in the project. 