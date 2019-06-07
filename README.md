# ValueBot

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

A simple discord bot for keeping track of points.

## What does it do?
Whenever you add a 👍 reaction to a message, the author of the message 
gains a point, likewise, if you react with a 👎, they lose a point.
The reaction emojis are configurable and can even be set to custom 
emojis.

You can inspect the amount of points you have using the `points` 
command, in doing so you will lose a point though. The same command
can also be used to inspect other user's points and server 
administrators can even use it to manipulate someone's points.

ValueBot also assigns roles based on the amount of points a user has.
The roles are configurable in the config file and can be disabled 
entirely.
