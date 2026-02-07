THE PROBLEM WITH LEAST SQUARES LOOP CLOSURES
by Larry Fish

Most cave surveyors assume that the best way to close a loop in a cave is to use an algorithm based on the "Least Squares/Simultaneous Equations" (LSSE) method. This is probably due to the fact that LSSE itself is based on sound mathematical and statistical methods and is widely used by land surveyors. It also partly due to the fact that it has the aura of being a complicated, sophisticated and esoteric algorithm. This idea is so pervasive, that no one ever examines the possibility that LSSE might have flaws when it comes to cave surveying. This is exactly why I am writing this article. I think that LSSE, although mathematically sound, is not the best method of CLOSING cave survey loops. I think that it is a very good tool being used for the wrong job.

Here is my argument in a nutshell: LSSE is a very powerful mathematical and statistical method with many uses. But, in terms of CLOSING cave loops, Least Squares/Simultaneous Equations is best suited for dealing with random errors that are evenly distributed across the whole cave. However, evenly distributed, random errors are not the biggest problem in cave surveying. Localized blunders are the biggest problem in cave surveying and LSSE does not handle blundered loops very well.

Let me give you some background. There are three kinds of errors that occur in cave surveys: random errors, systematic errors and blunders.

RANDOM ERRORS

Random errors are small errors that occur during the process of surveying. They result from the fact that it is impossible to get absolutely perfect measurements each time you read a compass, inclinometer or tape measure. For example, your hand may shake as you read the compass, the air temperature may affect the length of the tape, and you may not aim the inclinometer precisely at the target. There are literally hundreds of small variations that can affect your measurements. In addition, the instruments themselves have limitations as to how accurately they can be read. For example, most compasses don't have markings smaller than .5 degrees. This means that the actual angle may be 123.3 degrees, but it gets written down as 123.5.

All these effects add up to a small random variation in the measurement of survey shots. Around a loop, these random errors accumulate and cause a loop closure error. Even though these errors are random, the accumulated error tends to follow a pattern. The pattern is called a "normal" distribution and it has the familiar "bell" shaped curve. As a result of this pattern, we can predict how much error there should be in a survey loop if the errors are the result of small random differences in the measurements. If a survey exceeds the predicted level of error, then the survey must have another, more profound kind of error.

SYSTEMATIC ERRORS

Systematic errors occur when something causes a constant and consistent error throughout the survey. Some examples of systematic errors are: the tape has stretched and is 2 cm too long, the compass has a five degree clockwise bias, or the surveyor read percent grade instead of degrees from the inclinometer. The key to systematic errors is that they are constant and consistent. If you understand what has caused the systematic error, you can remove it from each shot with simple math. For example, if the compass has a five degree clockwise bias, you simply subtract five degrees from each azimuth. Systematic errors are usually dealt with by calibrating instruments on a survey course, or by adding correction factors to the survey data.

BLUNDERS

Blunders are fundamental errors in the surveying process. Blunders are usually caused by human errors. Blunders are mistakes in the processing of taking, reading, transcribing or recording survey data. Some typical blunders are: reading the wrong end of the compass needle, transposing digits written in the survey book, or tying a survey into the wrong station.

Blunders are the most difficult errors to deal with because they are inconsistent. For example, if you read the wrong end of the compass needle, the reading will be off by 180 degrees. If you transpose the ones and tens digits on tape measure, the reading could be off by anything from 0 to 90 feet.

HOW COMMON ARE BLUNDERS?

Blunders are extremely common in cave surveys. For example, in Lechuguilla Cave, 32 percent of the loops have blunders in them. In Wind Cave, 25 percent of the loops have blunders in them. (These are a conservative figure, because it is impossible to tell whether each loop has only one blunder in it.) By extrapolating I have concluded that in surveys like these, there is at least one blunder in every 40 shots.

Paul Burger did careful study of blunders during of a recent resurvey of the commercial section of Cave of the Winds. He found that one in 20 shots had a blunder. These figures are impressive, because these surveys were very carefully done in relatively easy, well lit, concrete-trailed walking passages. In more difficult caves, the blunder rate goes up rapidly. For example, in Groaning Cave, a cold, wet, alpine cave whose entrance is at 10,000 feet (3050 meters), 50 percent of the loops are blundered. All of this means that any survey with more than a few hundred shots, must have several blunders in it.

LEAST SQUARES AND RANDOM ERRORS

Let's start by looking at some of the characteristics of random errors. First of all, random errors, by their very nature, tend to be small. For example, you wouldn't expect to find random errors more much greater than an inch, a tenth of a meter or a degree in each shot.

The second important characteristic of random errors is that, over the long run, they have a tendency cancel each other out. This is easy to see. For example, sometimes you may read the compass slightly positive. Other times you may read the compass slightly negative. The net effect is the positives and negatives cancel out. Taken together, these two characteristics mean that the total error in loops with only random errors is relatively small.

The LSSE method is designed specifically to deal with random errors. It is in fact the best method of dealing with random errors. But if you have a survey that has ONLY random errors, it makes very little difference which algorithm you use! This is because the errors are so small that even a relatively simple algorithm will work as well as LSSE. In other words, there is no particular advantage to using LSSE if you have random errors.

Let me give you a real world example. I extracted a 1000 foot loop from Groaning Cave that had a relatively random looking error pattern. It was 64 stations long and had a 9 foot closure error. Analyzing the loop gives a standard deviation of about 1.0 (given a two degree variability in azimuth and inclination and .1 foot variability in length.) If you are not familiar with the concept, a standard deviation of 1.0 means that the error is about what you would expect if the errors are random. I closed this loop using both COMPASS and SMAPS and compared the result. SMAPS uses LSSE and COMPASS does not, so it a good way to analyze the difference. The difference between the two loops was less than .1 of a foot. I also did another experiment using a 2000 foot connected network of three loops of similar quality. The differences between SMAPS and COMPASS were less than .3 feet.

LEAST SQUARES AND BLUNDERS

Now lets look at blunders. One of the big selling points of LSSE is that it closes all the loops in the cave at simultaneously. This is exactly what you want when you have evenly distributed random errors, but with blunders it causes problems.

Let's look at this in detail. LSSE handles blunders in exactly the same way it handles errors. That is, it distributes them evenly across the cave. This would be fine if all the loops in the cave were either all good (with only random errors) or all bad (with only blunders), but that is rarely the case.

In the real world, most cave surveys have a mixture of both good and bad loops. If you have some good loops and some bad loops, least squares will take the errors and distribute them evenly across both the good and bad loops. This has the effect of contaminating the good loops with errors from the bad loops.

One way to deal with this problem is to design the LSSE algorithm so that you have independent control over how the program adjusts each shot. This is usually called something like the "confidence factor" and most LSSE implementations have this feature. Basically, you adjust this "confidence factor" to compensate for good and bad shots, surveys and loops. In other words, you give a higher confidence factor to the shots in the good loops and a lower confidence factor to the shots in the bad loops.

This almost works, except that you have a new problem: there will always be some shots that are shared by both good and bad loops! This creates a logical contradiction: you can't have a shot that is both good and bad at the same time. You could deal with this by setting the confidence factor for shared shots to a value halfway between a good and bad confidence factor. But, once again this would degrade the good loops by allowing a bad loop to alter shots in the good loop. The process is even more complicated if you have lots of loops which share common shots.

LOOP CLOSURE AND CAVE STATISTICS

The way you close loops has a profound effect on the accuracy of cave statistics. This is true anytime you have two parallel loops connecting parts of a cave. For example, let's say that you are trying to determine the depth of a cave and there are two loops that connect to the deep point. One loop closes very well, and the other loop has an large blunder in it. Obviously, to get the most accurate measurement of the cave's depth, you want to ignore all the shots in the blundered loop and only use the shots in the good loop. If you use LSSE, the errors from the blundered loop will contaminate the good loop degrading the accuracy of the depth measurement.

SHOULD BLUNDERED LOOPS EVEN BE CLOSED?

Some people say, that you shouldn't even try to close blundered surveys, and there is a good argument to be made for simply discarding all blundered loops and immediately redoing the survey. In fact, some survey programs refuse to close any loop that has a large error and appears to be blundered.

But, I think that blundered loops are exactly the reason you need loop closure. If a loop is good, it doesn't need much help from a loop closing algorithm. But if the loop is bad, it needs lots of help just to make the data even minimally useful.

The problem with discarding blundered surveys, is that it is difficult to get people to go back and resurvey caves. I have been trying for more than 10 years to get people to go back and resurvey the front part of Groaning Cave. Look at Lechuguilla. There are 245 loops with errors greater than three standard deviations. Wind cave has 132 loops with errors greater than three standard deviations. Chances are very slim that you are going to get people back in these caves to fix all the loops. For one thing, cavers aren't very excited about resurveying old passages. For another, the old survey stations are often lost, unreadable or moved, making the resurvey process much more complicated than just remeasuring the shots in an individual loop. At the very least, it can take years to correct bad loops.

In the mean time, people want maps and you can't draw very good maps from unclosed plots. If loops are left unclosed, all the errors in the loop pile up at the closing station. This creates plots with large offsets in the middle of passages or junctions where the angles are all wrong. When you try to draw a finished map around an unclosed loop, you have to nudge the lines around to make everything look right. In effect, you are closing the loops by hand. Obviously, in this day and age, when everyone has a computer, you shouldn't have to close loops by hand; even when there are large blunders. In fact, I think that the one of the most important purposes of loop closure in cave surveying is to make drawing maps easier!

THE BEST APPROACH TO LOOP CLOSURE

If least squares is not the best approach to loop closures in caves, what is? I think, the best approach has to accomplish three things:

1. It must be able to deal with blunders. 2. It must be able to deal with random errors. 3. It must be able to deal with a mixture of both.

The most important thing is that the data from in the good loops must be protected from the errors in bad loops. This implies that good loops must be closed separately from bad loops. Thus, the first step is to find the best and worst loops. This means sorting all of the loops in the cave according to quality. Basically, you want to locate all the individual loops, calculate standard deviations for each loop and then sort them into a list ordered from best to worst.

The next step is to close the loops in a way that segregates the good loops from the bad loops. You could use the LSSE method on all the good loops and then on all the bad loops as separate steps. This leads to a number of thorny problems like: what exactly is the threshold between good and bad, and what do you do with good loops that are separated from each other by bad loops?

The easiest way to close the loops separately, is to close the loops one-at-a-time taking the best loops first. Once a loop is closed, the shots in the loop must be protected or locked to prevent them from being adjusted along with subsequent loops. This technique has several advantages. First, because it doesn't require simultaneous equations it is much faster. Second, it perserves the accurracy of the best surveys, while at the same time isolating the errors and blunder to worst surveys where they belong.

ERROR ANALYSIS AND BLUNDER DETECTION

In addition to closing loops, a survey program should have the ability to detect and locate blunders. Detecting the existence of a blunder in a loop is fairly simple. You begin by making an estimate of the accuracy and variance of the survey instruments. From this, you can make a prediction of the size of error for each individual loop, the errors are random. To do this, you simply apply the variance of each instrument to each shot in the loop and calculate the standard deviation for the whole loop. Loops whose errors exceed two standard deviations have a greater than 95% chance of being blundered.

Locating the actual individual blundered measurement is more difficult, but, at least in some instances, is possible. The COMPASS blunder location process is described in detail in another article, but the basic process is simple. The program adjusts each measurement in the loop, trying to reduce the error as a much as possible. The adjustments that are most successful are the most likely candidate for blunders.

This generally results in several good candidates for the blundered measurement. To narrow the choices further, the program checks to see if the blunder candidates are a part of other loops. If a measurement is truly blundered, then it should show up as a blunder in every loop it is a part of. For example, if a shot is a part of five different loops, but appears to be blundered in only one of them it is very unlikely that it is the blunder.
