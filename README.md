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

## How to run the bot

If you want to miss out on the convenience of using [Heroku](https://heroku.com/deploy) and instead wish to do it manually then please, be my guest.

Make sure you have at least [Python 3.7](https://www.python.org/downloads/release/python-370/) installed.
First, you'll want to install the dependencies. To do this, you can use [pipenv](https://docs.pipenv.org) (`pip install pipenv`). 
Run `pipenv install` to install all required dependencies.

Before you can run the bot you need to setup the [PostgreSQL database](https://www.postgresql.org/). If you already happen to have one running, great, just adjust the `postgres_dsn` key in the [config.yml](config.yml) config file.
If you don't happen to have one lying around, I would recommend you just [run it locally using Docker](https://hackernoon.com/dont-install-postgres-docker-pull-postgres-bee20e200198). In this case you don't need to change the `postgres_dsn` key, as the default value is connecting to localhost. 

Finally, to start the bot use the command `pipenv run python -m valuebot`.
> If you install the dependencies without using pipenv you can just run `python -m valuebot` directly.
