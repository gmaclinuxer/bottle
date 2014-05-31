'''
Created on 2013-4-22

@author: Xsank
'''

from distutils.core import setup
from brick import version 

setup(name=version.__framework_name__,
      version=version.__version__,
      author=version.__author__,
      maintainer=version.__author__,
      maintainer_email=version.__email__,
      license=version.__license__,
      description=version.__description__,
      long_description=version.__detail__,
      author_email=version.__email__,
      url=version.__project_url__,  
      platforms=version.__platform__,
      packages=version.__packages__,
      )
