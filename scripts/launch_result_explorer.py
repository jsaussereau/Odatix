#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import webbrowser
from threading import Thread
from result_explorer import app

host_address = '127.0.0.1'
port = 8052

def open_browser():
    webbrowser.open(host_address + ':' + str(port), new=0, autoraise=True)

def close_server():
    sys.exit()

if __name__ == "__main__":
    from waitress import serve
    from flask import request

    # Open the web page
    process = Thread(target=open_browser).start()

    # Start the server
    serve(app.server, host=host_address, port=port)