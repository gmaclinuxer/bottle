'''
Created on 2013-4-22

@author: Xsank
'''

import sqlite3 

from exception import DatabaseOperationError


class SQLite(object):
    def __init__(self,database):
        self.database=database
        
    def __str__(self):
        return self.database
        
    def __del__(self):
        self.close()
        
    def connect(self):
        self.conn=sqlite3.connect(self.database)
        self.cursor=self.conn.cursor()
        return self
    
    def close(self):
        if hasattr(self,"conn") and self.conn:
            self.conn.close()
        
    def execute(self,sql_query=None):
        if not sql_query:
            raise DatabaseOperationError
        try:
            self.cursor.execute(sql_query)
        except DatabaseOperationError:
            pass
    
    def fetch_one(self,sql_query=None):
        self.execute(sql_query)
        return self.cursor.fetch_one
    
    def fetch_all(self,sql_query):
        self.execute(sql_query)
        return self.cursor.fetch_all()
    
    
    
            