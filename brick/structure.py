'''
Created on 2013-4-21

@author: Xsank
'''

from collections import MutableMapping as DictMixin


class MultiDict(DictMixin):
    def __init__(self, *a, **k):
        self.dict = dict()
        for k, v in dict(*a, **k).iteritems():
            self[k] = v

    def __len__(self): return len(self.dict)

    def __iter__(self): return iter(self.dict)

    def __contains__(self, key): return key in self.dict

    def __delitem__(self, key): del self.dict[key]

    def __getitem__(self, key): return self.get(key, KeyError, -1)

    def __setitem__(self, key, value): self.append(key, value)

    def keys(self): return self.dict.keys()

    def append(self, key, value): self.dict.setdefault(key, []).append(value)

    def replace(self, key, value): self.dict[key] = [value]

    def getall(self, key): return self.dict.get(key) or []

    def get(self, key, default=None, index=-1):
        if key not in self.dict and default != KeyError:
            return [default][index]
        return self.dict[key][index]

    def iterallitems(self):
        for key, values in self.dict.iteritems():
            for value in values:
                yield key, value
                

class HeaderDict(MultiDict):
    def __contains__(self, key): return MultiDict.__contains__(self, self.httpkey(key))

    def __getitem__(self, key): return MultiDict.__getitem__(self, self.httpkey(key))

    def __delitem__(self, key): return MultiDict.__delitem__(self, self.httpkey(key))

    def __setitem__(self, key, value): self.replace(key, value)
    
    def get(self, key, default=None, index=-1): return MultiDict.get(self, self.httpkey(key), default, index)

    def append(self, key, value): return MultiDict.append(self, self.httpkey(key), str(value))

    def replace(self, key, value): return MultiDict.replace(self, self.httpkey(key), str(value))

    def getall(self, key): return MultiDict.getall(self, self.httpkey(key))

    def httpkey(self, key): return str(key).replace('_','-').title()