'''
Created on 2013-4-21

@author: Xsank
'''

from brick.brick import route,get,post,run,redirect,send_file
from brick.brick import request
from brick.template import template

from util import load_page,save_page,load_words


@route('/')
def index():
    return template('index',**load_words())


@get('/view/:name')
def view(name):
    return template('view',**load_page(name))


@route('/edit/:name')
def edit(name):
    return template("edit",**load_page(name))


@post('/save')
def save():
    save_page(request.POST['name'],request.POST['body'])
    redirect("view/%s" % request.POST['name'])


@route("/static/:filename")
def static_file(filename):
    send_file(filename,root="static")


run(host='localhost',port=8080)



