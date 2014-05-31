Brick Web Framework
====================


Brick is a mini web framework which is derived from Bottle. Brick have the same 
function of the Bottle. I do these just because bottle is only one file, i want 
to separate the function of the framework so that i can learn it more easily.

License: MIT (see LICENSE)

Installation and Dependencies
-----------------------------

Install brick 

git clone https://github.com/xsank/bottle.git

python setup.py install


Example
-------

.. code-block:: python

    from brick.brick import route,get,post,run,send_file
    from brick.brick import request
    from brick.template import template

    from util import load_words


    @route('/')
    def index():
        return template('index',**load_words())
        
    @route("/static/:filename")
    def static_file(filename):
        send_file(filename,root="static")
        
        
    run(host='localhost',port=8080)


I also use the Brick write an mini wiki project to test, all the source code is in example directory.
