# Survey Data Format: Compass DAT

The COMPASS survey data files contain all the original measurements and
associated information that make up the original survey data. They are
ordinarily created by the COMPASS Survey Editor; but under special
circumstances, they can be edited with an ordinary text editor as long
as the file format is maintained.. **Warning!**Unless you have a
thorough understanding of your editor and ASCII character codes, it is
not advisable to directly edit COMPASS survey files. Most word processor
will change the format of the survey data and this will corrupt the
data. If you need to directly edit survey data, you should use
**XEDIT,** a text editor that was designed to not corrupt ASCII data. It
is available on the [[Fountain home
page](http://fountainware.com/)]{.underline} or on the COMPASS CD-ROM.

This section describes in detail the current raw survey data format.
Listed below you will see a sample survey file. The layout has been
compressed slightly so the file will fit on the page, but all the fields
are correct:

```
<Cave Name>
SURVEY NAME: <Name of Survey>
SURVEY DATE: <Name of Survey: D MM YYYY//YY>  COMMENT: <Comment>
SURVEY TEAM:
<Comma Separated Names: John A,John B,...>
DECLINATION: <DECL: float>  [FORMAT: <FORMAT_STR>  CORRECTIONS: <CORR_STR> CORRECTIONS2: <CORR2_STR>]:optionals


        FROM           TO   LENGTH  BEARING  DIP/INC     LEFT       UP     DOWN    RIGHT    [AZM2     INC2   FLAGS  COMMENTS]: Optional
<Linebreak>
         z23         toc0     8.20    71.00    38.00     0.00     0.00     0.00     0.00   253.00   -38.00
        toc0         toc1    14.10  -999.00    90.00     0.00     0.00     0.00     0.00     0.00  -999.00
        toc1         toc2    18.50   131.00     0.50     0.00     0.00     0.00     0.00   312.00    -1.00
        toc2         toc3    16.20   197.00     0.50     0.00     0.00     0.00     0.00    17.00    -1.00
<form feed>
```

1. **Individual Surveys.**
You will notice that the file contains data for two individual surveys. COMPASS survey files can have any number of surveys within a single file. All surveys end with a Form Feed character on a separate line. Thus, if there are multiple surveys in a file, each survey is separated by a form feed. A Form Feed character is the equivalent of a Control-L in some editors or 0C hex. If you choose to edit a survey file with a text editor, make sure you understand how to enter a Form Feed and how it is displayed. Otherwise, it is easy to accidentally delete the Forms Feeds, which will corrupt the file.

2. **The Header.**
Each survey begins with a header that gives information about the survey that will follow. The following list describes each header item:

   1. **Cave Name (Line 1).** The first line contains the cave name. It can be any alphanumeric characters up to 80 characters in length. It is terminated by a carriage return and line feed. For the most part, the software ignores the cave name.
 
   2. **Survey Name (Line 2).** The survey name is usually the alphabetic prefix that is attached to each survey station. For example, if the survey name is AB, then the individual survey stations will be AB1, AB2, AB3, etc. The survey name field begins with the string: \"SURVEY NAME: \", which is followed by the actual survey name. The name can be any printable ASCII character and is terminated by the first white space character, usually end-of-line characters. It can be up to 12 characters in length.
 
   3. **Survey Date (Line 3).** The date field begins with the string \"SURVEY DATE: \" and is followed by three numerical date fields: month, day and year. The year can be a two digit or four digit number, i.e. 1992 or 92.
 
   4. **Survey Comment (Line 3).** For backward compatibility, this item is optional. It is used to describe the survey in more detail than the Survey Name. The survey comment begins with the string \"COMMENT:\" and is terminated by the Carriage Return at the end of the line. The actual comment begins immediately after the colon \":\" character.
 
   5. **Survey Team (Line 4).** The survey team fields consists of two lines. The first line contains the string: \"SURVEY TEAM:\" No other information appears on this line. The next line holds the actual survey team information. The survey team information can be up to 100 characters in length. There is no specific format to this information. It is up to the user.
 
   6. **Declination (Line 5).** The declination field gives the magnetic declination for a particular region. It is used to compensate for local magnetic anomalies and differences between compasses. The declination field begins with the string \"DECLINATION: \" followed by a floating point number. This number is added to the azimuth of each shot in the survey.
 
   7. **File Format (Line 5).** For backward compatibility, this item is optional. This field specifies the format of the original survey notebook. Since COMPASS converts the file to fixed format, this information is used by programs like the editor to display and edit the data in original form. The field begins with the string: \"FORMAT: \" followed by 11, 12 or 13 upper case alphabetic characters. Each character specifies a particular part of the format. Here is list of the format items:


| **Position** | **Possible Values & Meaning**                                                                                               |
|:------------:|:---------------------------------------------------------------------------------------------------------------------------:|
| **I.**       | Bearing Units: **D** = Degrees, **Q** = quads, **R** = Grads                                                                |
| **II.**      | Length Units: **D** = Decimal Feet, **I** = Feet and Inches **M** = Meters                                                  |
| **III.**     | Passage Units: **D** = Decimal Feet, **I** = Feet and Inches **M** = Meters                                                 |
| **IV.**      | Inclination Units: **D** = Degrees, **G** = Percent Grade, **M** = Degrees and Minutes,  **R** = Grads, **W** = Depth Gauge |
|              |                                                                                                                             |
| **V.**       | Passage Dimension Order: **U** = Up, **D** = Down, **R** = Right **L** = Left                                               |
| **VI.**      | Passage Dimension Order: **U** = Up, **D** = Down, **R** = Right **L** = Left                                               |
| **VII.**     | Passage Dimension Order: **U** = Up, **D** = Down, **R** = Right **L** = Left                                               |
| **VIII.**    | Passage Dimension Order: **U** = Up, **D** = Down, **R** = Right **L** = Left                                               |
|              |                                                                                                                             |
| **IX.**      | Shot Item Order: **L** = Length, **A** = Azimuth, **D** = Inclination                                                       |
| **X.**       | Shot Item Order: **L** = Length, **A** = Azimuth, **D** = Inclination                                                       |
| **XI.**      | Shot Item Order: **L** = Length, **A** = Azimuth, **D** = Inclination                                                       |
|              |                                                                                                                             |
| **XII.**     | Backsight: **B** = Redundant, **N or **empty** = No Redundant Backsights                                                    |
| **XIII.**    | LRUD Association: **F** = From Station, **T** = To Station                                                                  |


   8. **Instrument Correction Factors (Line 5).** For backward
compatibility, this item is optional. The item begins with the string
\"CORRECTIONS:\" The Instrument Correction Factors are used to correct
defective instrument readings. There are three numbers that are used to
correct the compass, inclinometer and tape readings respectively. These
values are added to the azimuth, inclination and length values for the
survey. The azimuth and inclination readings are in degrees and the
length value is in feet.
 
   9. **Back Sight Instrument Correction Factors (Line 5).** For backward
compatibility, this item is optional. The item begins with the string
\"CORRECTIONS2:\" The Instrument Correction Factors are used to correct
defective instrument readings for Back Sights There are two numbers that
are used to correct the compass and inclinometer readings respectively.
These values are added to the back sight azimuth and inclination values
for the survey. The azimuth and inclination readings are in degrees.

3. **Survey Shots.** Following the header are three lines which serve to
separate the header from the shots. The middle line identifies each
field in the shot. Their purpose is only to make the file more readable.
They are ignored by all software.
Following the separating lines is a series of shots. Each shot is
contained on a single line. There are eleven possible items on the line.
Some items are optional.

   1. **From Station.** The first item on the line is the \"from\" survey
station name. It consists of up to 12 printable ASCII characters. It is
terminated by the first white space character. It is case sensitive. In
the normal situation, the \"from\" station is defined as the station
whose location has already been established, whereas the \"to\" station
is the station whose location is about to be established. In the case of
a backsight, the reverse is true.
 
   2. **To Station.** The second item on the line is the \"to\" survey
station name. It consists of up to 12 printable ASCII characters. It is
terminated by the first white space character. It is case sensitive.
 
   3. **Length.** This is the length of the shot between the from and to
stations. It is a single floating point number of virtually any format.
It is terminated by the first white space character. It specifies length
in decimal feet.
 
   4. **Bearing.** This item specifies the compass angle of the shot. It is
a single floating point number of virtually any format. It is terminated
by the first white space character. It specifies bearing in decimal
degrees.
 
   5. **Inclination.** This is the angle of inclination of the shot. It is
a single floating point number of virtually any format. It is terminated
by the first white space character. It specifies inclination in decimal
degrees.
 
   6. **Left.** This is the distance between the station and the left wall.
It is a single floating point number of virtually any format. It is
terminated by the first white space character. It specifies distance in
decimal feet.
 
   7. **Up.** This is the distance between the station and the ceiling. It
is a single floating point number of virtually any format. It is
terminated by the first white space character. It specifies distance in
decimal feet.
 
   8. **Down.** This is the distance between the station and the floor. It
is a single floating point number of virtually any format. It is
terminated by the first white space character. It specifies distance in
decimal feet.
 
   9. **Right.** This is the distance between the station and the right
wall. It is a single floating point number of virtually any format. It
is terminated by the first white space character. It specifies distance
in decimal feet.
 
   10. **Azm2.** For backward compatibility, this is an optional item. It is
turned on or off with the File Format item in the header. If redundant
backsights are enabled, this is the backsighted azimuth value. The
second survey in the listing above has backsights enabled. This value is
always stored uncorrected, so it should be 180 degrees from the bearing.
An editor may choose to display it as a corrected backsight, in which
case, it should equal the bearing.<br>
 **Note:** redundant backsights are different from ordinary backsights. A
redundant backsight consists of an extra compass and inclination
reading. This is normally done to increase the accuracy of a survey. An
ordinary backsight occurs where it is more convenient to measure a shot
in reverse order. For example, you could do an ordinary backsight when
there is a rock that interferes with the \"from\" station. In COMPASS,
ordinary backsights are simply entered in reverse. COMPASS is expected
to notice that the shot is reversed and handle it.
 
   11. **Inc2.** For backward compatibility, this is an optional item. It is
turned on or off with the File Format item in the header. If redundant
backsights are enabled, this is the backsighted inclination value. The
second survey in the listing above has backsights enabled. This value is
always stored uncorrected, so it should be the same value as the
inclination with sign changed. An editor may choose to display it as a
corrected backsight, in which case, it should equal the inclination.
 
   12. **Flags.** For backward compatibility, this is an optional item. It
specifies a set of flags that modify the way in which this shot is
processed. To distinguish the flag field from the comment field that
follows, flags must be preceded by two characters, a pound sign and a
vertical bar: \"#\|\". This is followed by up to three printable
characters. The flag field is terminated by a single pound sign \"#\"
character. At this time there are four flags that are recognized:
 
L - Exclude this shot from length calculations.
P - Exclude this shot from plotting.
X - Exclude this shot from all processing.
C - Do not adjust this shot when closing loops.
 
   13.  **Comments.** For backward compatibility, this field is optional. It
contains a comment pertaining to this shot. It can be up to 80
characters in length, and it terminates at the end-of-line.

## Important Note

**Line Length.** Lines in survey files may be longer than the normal
computer screen width. When working with them in non-COMPASS editors, be
sure that the editor does not wrap the lines around, or the file may be
corrupted when saved.