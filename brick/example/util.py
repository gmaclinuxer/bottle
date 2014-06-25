import markdown


def load_page(name):
    try:
        body=open("pages/"+name+".md").read().decode("utf-8")
    except:
        body=u'Empty Page'
    body_html=markdown.markdown(body).encode('utf-8')
    return dict(name=name,body=body,body_html=body_html)


def load_words():
    try:
        words=open("pages/Index.md").readlines()
    except Exception,e:
        words=u"No Words"
    return dict(words=words)


def save_page(name,body):
    with open("pages/"+name+".md",'w') as f:
        f.write(body)
    with open("pages/Index.md",'a') as f:
        f.write('\n'+name)