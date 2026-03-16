#!/usr/bin/env python3

# aedit.py
# https://github.com/Daniele71/aedit
#
# script for creating report about
# Ardour sessions (session info, used plugins)
# It can also remove plugin. ONLY FOR TESTING BROKEN PLUGIN !!!!
#
# license: MIT

# IMPORTS
import xml.etree.ElementTree as etree
import sys
import argparse
import os
from time import sleep, time
from datetime import datetime
import locale
from shutil import copy2
import re


# CLASS
class sessionParser():
    def __init__(self):
        # vars
        self.name = 'aedit'
        self.version = '1.0.0'
        self.plugins_type = ('vst2', 'vst3', 'luaproc', 'clap', 'lv2', 'lxvst')
        self.__setAndResetAll()
        self.removed = 0
        self.deleted_plugins = {}
        self.afile = None
        # damned window
        if sys.platform.lower() == 'win32':
            # fix windows ANSI escape
            os.system('')
        elif sys.platform.lower() == 'linux':
            # just to avoid some garbage with input()
            import readline
        # argparse
        self.aparser = argparse.ArgumentParser()
        self.aparser.add_argument("-f", '--file', help="Session file (*.ardour)", default=None)
        self.aparser.add_argument("-s", '--save', action='store_true', help="Save a text report/Mutliple report with -d")
        self.aparser.add_argument("-n", '--nopath', action='store_true', help="Hide path for privacy")
        self.aparser.add_argument("-d", '--dir', default=None, help="Ardour sessions dir")
        self.aparser.add_argument("-i", '--info', action='store_true', help="Show some system info")
        self.args, self.wronghargs = self.aparser.parse_known_args()
        if self.wronghargs:
            self.errormsg = 'Invalid option '+str(self.wronghargs)
            self.__printError()
            self.aparser.print_usage()
            sys.exit(1)
        # parse arguments: -f takes precedence:
        if self.args.file:
            self.__parseSessionFile()
        # check for -d option
        if self.args.dir:
            self.__parseSessionsDir()
            # remove ?
            sys.exit()
        # info
        if self.args.info:
            print(self.__sysInfoText())
            sys.exit(0)
        # no options
        self.__mainMenu()


    # remove path for privacy
    def __noPath(self, path, force = False):
        if self.args.nopath or force:
            return os.path.basename(path)
        return path
    
    # Remove ANSI escape codes for report
    def __removeANSI(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


    # current date with localization
    def __today(self):
        try:
            locale.setlocale(locale.LC_TIME, locale.getlocale())
        except locale.Error:
            # fallback to 'C'
            locale.setlocale(locale.LC_TIME, 'C')
        today: datetime = datetime.now()
        return f'{today:%x}'


    # parse session file (*.ardour)
    def __parseSessionFile(self):
        # check for file
        self.afile = os.path.abspath(self.args.file)
        # is a valid file ?
        if not os.path.isfile(self.afile):
            print('\n-> ', self.__noPath(os.path.abspath(self.afile)))
            self.errormsg = "Not a file..."
            self.__printError()
            self.__mainMenu()
        # parse session file
        if not self.__parseArdourFile(self.afile):
            self.__printError()
            return
        self.__createPluginsList()
        # report
        if self.args.save:
            self.__saveToTextFile()
            sys.exit()
        self.printAll()
        self.__printMenu()


    # parse Sessions dir
    def __parseSessionsDir(self):
        tstart = time()
        content = ''
        self.wdir = os.path.abspath(self.args.dir)
        # is a valid dir ?
        if not os.path.isdir(self.wdir):
            print('\n-> ', self.__noPath(self.wdir))
            self.errormsg = "Not a Dir. Wrong Path ?"
            self.__printError()
            sys.exit()
        path = os.path.abspath(self.wdir)
        if not os.access(path, os.W_OK):
            print('Session path not readable')
            syx.exit()
        print('\nSessions Dir: ', self.__noPath(path), '\n')
        # counters
        self.parsed_count = 0
        self.parsed_error = 0
        self.parsed_skipped = 0
        for d in os.listdir(path):
            if os.path.isdir(os.path.join(path, d)):
                if os.path.isfile(os.path.join(path, d, d+'.ardour')):
                    fname = d+'.ardour'
                    self.afile = os.path.join(path, d, d+'.ardour')
                    print(self.__formatString('Parsing: '+self.__noPath(self.afile), 105), end='')
                    if self.__parseArdourFile(self.afile):
                        self.__createPluginsList()
                        self.parsed_count +=1
                        ###
                        # single file
                        if self.args.save:
                            content += self.__prepareReport()
                            print(self.__colorize('Ok!', 'green'))
                            self.__setAndResetAll()
                        else:
                            print(self.__colorize('Ok!', 'green'))
                            if not self.__saveToTextFile():
                                self.parsed_error +=1
                            print('')
                    else:
                        # wrong *.ardour file
                        print(self.__colorize('Skipped!', 'orange'))
                        print(self.__colorize('['+self.errormsg+']', 'grey'))
                        self.parsed_skipped += 1
                        print('')
                else:   
                    # print('Error : ', os.path.join(path, d, d+'.ardour'))
                    print(self.__formatString('\nParsing: '+self.__colorize(self.__noPath(os.path.join(path, d, d+'.ardour')), 'grey'), 111), end='')
                    print(self.__colorize('Failed!', 'red'))
                    print(self.__colorize('[Missing/Invalid file]', 'grey'), '\n')
                    self.parsed_error +=1
                    sleep(0.8)
        # how faster are we ?
        # we add 0.02  'cause file write happens later ;)
        tend = "%.3fs" % (time() - (tstart+0.02))
        print('\nCompleted!', self.__colorize('('+tend+')', 'grey'))
        if content:
            #print('Saving full report\n')
            self.__writeReport(path, content)
        else:
            print(self.__scanResults())
        # clean up and reset
        self.__setAndResetAll()
        self.removed = 0
        self.deleted_plugins = {}
        self.afile = ''

    # scan results
    def __scanResults(self):
        res = 'Parsed Sessions: '+str(self.parsed_count)+'  Good: '+ str(self.parsed_count-self.parsed_error)+'  Error: '+ str(self.parsed_error)+ '  Skipped: '+ str(self.parsed_skipped)+ '\n'
        return res + '-'*98+'\n'


    ## write single report
    def __writeReport(self, path, data):
        fname = 'sessions_report.txt'
        rfile = os.path.join(path, fname)
        print(self.__scanResults())
        print(self.__formatString('\nSaving report to: '+str(self.__noPath(rfile)), 106), end='')
        content = 'Report created with '+self.name+' '+self.version+' - '+self.__today()+'\n'
        content += self.__scanResults()+data
        # return
        if self.__fileWrite(rfile, content):
            sleep(0.4)
            print(self.__colorize("Ok!", 'green'))
            sleep(0.4)
        else:
            print(self.__colorize("FAILED!", 'red'))
            print(self.__colorize(self.writeerror, 'grey'))


    # parse session file (*.ardour)and set basic info
    def __parseArdourFile(self, afile):
        try:
            self.etree = etree.parse(afile)
        except (etree.ParseError, PermissionError) as ex:
                self.errormsg = type(ex).__name__+' - Invalid file ?'
                return False
        self.eroot = self.etree.getroot()
        # get basic info
        self.session_name = self.eroot.attrib['name']
        self.session_version = self.eroot.attrib['version']
        self.session_sr = self.eroot.attrib['sample-rate']
        ee = self.eroot.find('ProgramVersion')
        self.created_with = ee.attrib['created-with']
        self.modified_with = ee.attrib['modified-with']
        return True


    # remove plugin from tree
    # num = plugin number
    def __removeplugin(self, num):
        num = int(num)
        if None == self.plugins_store.get(num):
            self.errormsg = "Invalid Plugin number: "+str(num)
            self.__printError()
            return False
        for child in self.eroot:
            for ee in child.findall('Route'):
                for pr in ee.findall('Processor'):
                    if pr.attrib['type'] in self.plugins_type:
                        # print(pr.attrib['name'])
                        # remove plugin with this id
                        if pr.attrib['id'] == self.plugins_store[num]:
                            # print(pr.attrib['name'])
                            print(self.__formatString('\nPlugin n.'+str(num)+' "'+pr.attrib['name']+'": ', 80), end='')
                            ee.remove(pr)
                            sleep(0.3)
                            self.removed += 1
                            self.__addRemovedPlugin(ee.attrib['name'], pr.attrib['name'])
                            print(self.__colorize("REMOVED!", 'green'))
                            sleep(0.5)
                            return True


    # create plugins list
    def __createPluginsList(self):
        for child in self.eroot:
            for ee in child.findall('Route'):
                tr = self.__boldfier(self.__colorize(ee.attrib['name'], 'blue'))
                self.tracks_count += 1
                dt = ' | '+self.__colorize(ee.attrib['default-type'], 'grey')+'\n'
                self.plugins_list += '\n'+tr+dt
                for pr in ee.findall('Processor'):
                    if pr.attrib['type'] in self.plugins_type:
                        self.num += 1
                        self.plugins_store[self.num] = pr.attrib['id']
                        if pr.attrib['type'] == 'lv2':
                            self.__addPluginToList(pr.attrib['name'], 'lv2')
                            self.nlv2 += 1
                        elif pr.attrib['type'] == 'vst2':
                            self.__addPluginToList(pr.attrib['name'], 'vst2')
                            self.nvst2 += 1
                        elif pr.attrib['type'] == 'vst3':
                            self.__addPluginToList(pr.attrib['name'], 'vst3')
                            self.nvst3 += 1
                        elif pr.attrib['type'] == 'lxvst':
                            self.__addPluginToList(pr.attrib['name'], 'lxvst')                            
                            self.nlxvst += 1
                        elif pr.attrib['type'] == 'luaproc':
                            self.__addPluginToList(pr.attrib['name'], 'lua')                            
                            self.nlua += 1
                        elif pr.attrib['type'] == 'clap':
                            self.__addPluginToList(pr.attrib['name'], 'clap')                            
                            self.nclap += 1


    # store removed plugin with track name as key
    def __addRemovedPlugin(self, tname, pname):
        if tname in self.deleted_plugins:
            self.deleted_plugins[tname].append(pname)
        else:
            self.deleted_plugins[tname] = [pname]


    # set/reset all vars before (re)scan
    def __setAndResetAll(self):
        self.num = 0
        self.total_plugins = 0
        self.plugins_store = {}
        self.plugins_list = ''
        self.nlv2 = self.nvst2 = self.nvst3 = self.nlxvst = self.nlua = self.nclap = 0
        self.tracks_count = 0

    # add plugin to list
    def __addPluginToList(self, pname, ptype):
        num = ' '+str(self.num)+')'
        num = self.__formatString(num, 7)
        self.plugins_list += self.__formatString(num+pname, 93)+str(ptype)+'\n'


    # print error message
    # and wait a bit
    def __printError(self):
        print(self.__colorize(self.__boldfier('# ERRROR ! : '), 'red')+self.errormsg)
        sleep(0.5)


     # format stringa
    def __formatString(self, st1, nn):
        return f"{st1:<{nn}}"


    # prepare info text
    def __infoText(self):
        recapinfo = self.__boldfier('\nINFO:\n')
        recapinfo += self.__formatString(' Session:', 20)+self.session_name+'\n'
        recapinfo += self.__formatString(' Version:', 20)+self.session_version+'\n'
        recapinfo += self.__formatString(' Sample Rate:', 20)+str(self.session_sr)+" hz\n"
        recapinfo += self.__formatString(' Tracks:', 20)+str(self.tracks_count)+"\n"
        recapinfo += self.__formatString(" Created with:", 20)+self.created_with+'\n'
        recapinfo += self.__formatString(" Modified with:", 20)+self.modified_with+'\n'
        recapinfo += self.__formatString(' Session file:', 20)+self.__noPath(self.afile)+'\n'
        recapinfo += '-'*98
        return recapinfo


    # recap plugins
    def __recapText(self):
        self.total_plugins = self.nlv2 + self.nvst2 + self.nvst3 + self.nlxvst + self.nlua + self.nclap
        recaptext = self.__formatString(self.__boldfier('\nPLUGINS:'), 30)+str(self.total_plugins)+'\n'
        recaptext += self.__formatString(' lv2:', 20)+str(self.nlv2)+'\n'
        recaptext += self.__formatString(' vst2:', 20)+str(self.nvst2)+'\n'
        recaptext += self.__formatString(' vst3:', 20)+str(self.nvst3)+'\n'
        recaptext += self.__formatString(' lxvst:', 20)+str(self.nlxvst)+'\n'
        recaptext += self.__formatString(' lua:', 20)+str(self.nlua)+'\n'
        recaptext += self.__formatString(' clap:', 20)+str(self.nclap)+'\n'
        recaptext += '-'*98
        return recaptext


    # prepare plugin list
    def __pluginText(self):
        pltext = self.__boldfier('\nTRACK/PLUGIN LIST:\n')
        pltext += self.plugins_list+'-'*98+'\n'
        return pltext


    # colorize text
    # valid color: red, grey, green, orange, blue
    # default reset to default color
    def __colorize(self, text, color='default'):
        colors = {'red': '\033[31m', 'grey': '\033[90m', 'green': '\033[32m', 'default': '\033[0m', 'orange':'\033[33m', 'blue':'\033[94m'}
        return colors.get(color, '\033[0m')+text+"\033[0m"


    # boldfier return bold text
    # not on windows cmd
    def __boldfier(self, text):
        return "\033[01m"+text+"\033[0m"


    # prepare report. Return all data wihout ANSI code
    def __prepareReport(self):
        report = self.__infoText()
        report += '\n'+self.__recapText()
        report += '\n'+self.__pluginText()+'\n\n'
        return self.__removeANSI(report)
    

    # print results
    def printAll(self):
        print(self.__infoText())
        print(self.__recapText())
        print(self.__pluginText())


    # print menu
    def __printMenu(self):
        menu = self.__boldfier('\033[04m\nEDIT ACTIONS:\033[0m\n')
        if self.deleted_plugins:
            menu += "w) re-Write session file"
            menu += self.__colorize(' (!)', 'grey')+'\n'
            menu += "v) View changes"+self.__colorize(" ("+str(self.removed)+')', 'grey')+'\n'
        else:
             menu += self.__colorize("w) re-Write session file", 'grey')+'\n'
             menu += self.__colorize("v) View changes", 'grey')+'\n'
        #menu += '\n'
        menu += "s) Save to text file\n"
        if self.total_plugins == 0:    
            menu += self.__colorize("r) Remove plugin\n", 'grey')
        else:
             menu += "r) Remove plugin\n"
        menu += "m) Main Menu\n"
        menu += "q) Quit\n"
        print(menu)
        sel = input("Enter option: ")
        if sel == 's':
            self.__saveToTextFile()
            sleep(0.5)
        elif sel == 'q':
            self.__confirmExit()
        elif sel == 'r':
            self.__pluginMenu()
        elif sel == 'w':
            if not self.__dumpSessionFile():
                self.__printError()
        elif sel == 'm':
            self.__mainMenu()
        elif sel == 'v':
            self.__viewChanges()
        else:
            self.errormsg = 'Invalid option\n'
            self.__printError()
        self.__printMenu()


    # view deleted plugins
    def __viewChanges(self):
        #if self.removed:
        if self.deleted_plugins:
            print('\n')
            print(self.__boldfier('\033[04mREMOVED PLUGINS:\033[0m\n'))
            for k in self.deleted_plugins:
                print(self.__formatString(self.__colorize(k+':', 'blue'), 56))
                for v in self.deleted_plugins[k]:
                    print('- ', v)
            print('-'*98)
        else:
            print("\nThere's no changes !")
            sleep(0.5)
        self.__printMenu()


    # main menu when
    def __mainMenu(self):
        menu = '\nWellcome to '+self.name+' '+self.version+' - '+self.__today()+'\n\n'
        menu += self.__boldfier('\033[04mMAIN ACTIONS:\033[0m\n')
        menu += "f) Load *.ardour file\n"
        menu += "s) Sessions Report (multiple files)\n"
        menu += "d) Sessions Report (single file)\n"
        # loaded file ?
        if not self.afile:
            menu += self.__colorize("e) Edit Ardour file\n", 'grey')
        else:
            menu += "e) Edit Ardour file ("+self.__colorize(self.__noPath(self.afile, True), 'grey')+")\n"
        menu += "q) Quit\n"
        menu += 'i) Info'
        print(menu)
        sel = input("Enter option: ")
        if sel == 'f':
            o = input('File: ')
            if not str(o).lower() == '':
                self.args.file = o
                self.__parseSessionFile()
            else:
                self.errormsg = "Enter a file name"
                self.__printError()
        elif sel == 'q':
            self.__confirmExit()
        elif sel == 's':
            o = input('Sessions Dir: ')
            if not str(o).lower() == '':
                self.args.dir = o
                self.args.save = False
                self.__parseSessionsDir()
            else:
                self.errormsg = "Invalid Option"
                self.__printError()
        elif sel == 'd':
            o = input('Sessions Dir: ')
            if not str(o).lower() == '':
                self.args.dir = o
                self.args.save = True
                self.__parseSessionsDir()
            else:
                self.errormsg = "Invalid Option"
                self.__printError()
        elif sel == 'e':
            if not self.afile:
                print('No Ardour file loaded')
                sleep(0.5)
                self.__mainMenu()
            else:
                self.printAll()
                self.__printMenu()
        elif sel == 'i':
            print(self.__sysInfoText())
            sleep(0.5)
        else:
            self.errormsg = 'Invalid option\n'
            self.__printError()
        self.__mainMenu()


    # print some info
    def __sysInfoText(self):
        text = self.__boldfier('\033[04m\nSYSTEM INFO:\033[0m\n')
        text += 'Program: '+self.name+' - '+self.version+'\n'
        text += 'OS: '+sys.platform+'\n'
        text += 'Pyhton: '+str(sys.version_info.major)+'.'+str(sys.version_info.major)+'.'+str(sys.version_info.micro)+'\n'
        text += 'Project page: https://github.com/Daniele71/aedit\n'
        text += '-'*50
        return text


    # confirm exit, if needed
    def __confirmExit(self):
        # if self.removed:
        if self.deleted_plugins:
            sel = input(str(self.removed)+' unsaved changes. Quit anyway ? y/N: ')
            sel = str(sel).lower()
            if sel == 'y':
                sys.exit()
            else:
                self.__printMenu()
        else:
            sys.exit()


    # rewrite ardour file
    # we do a backup first..
    def __dumpSessionFile(self):
        if not self.removed:
            print('Nothing to save')
            sleep(0.7)
            self.__printMenu()
            return
        sel = input('Overwriting file '+self.__noPath(self.afile)+ '? Y/n: ')
        sel = str(sel).lower()
        if sel in ('', 'y'):
            try:
                # backup original file
                try:
                    bu = os.path.join(os.path.dirname(self.afile), self.session_name+'.save')
                    print(self.__formatString('Saving backup to: '+self.__noPath(bu), 84), end = '')
                    if copy2(self.afile, bu):
                        print(self.__colorize('Ok', 'green'))
                        sleep(0.5)
                except (IOError, FileNotFoundError, PermissionError, OSError) as ex:
                    er = type(ex).__name__
                    print('Error backuping file: ', er)
                    sel = input('Continue anyway ? y/n')
                    if str(sel).lover() == 'n':
                        print('Aborting...')
                        sleep(1.0)
                        return False
                print(self.__formatString('Writing: '+self.__noPath(self.afile), 84), end='')
                # few not mandatory fixes here:
                # 1) elementree writes xml headers with (') instead of (")
                # 2) closing tag  ' />' instead of '/>'
                # thus file.write is used instead of elementree.write()
                fd = etree.tostring(self.eroot)
                xml_str = '<?xml version="1.0" encoding="UTF-8"?>' + '\n' +fd.decode("utf8")
                xml_str=xml_str.replace(' />', '/>')
                with open(str(self.afile), 'w') as tfile:
                    tfile.write(xml_str)
            except (IOError, FileNotFoundError, PermissionError, OSError) as ex:
                print(self.__colorize('Failed!', 'red'))
                self.errormsg = type(ex).__name__
                return False
            print(self.__colorize('Done!', 'green'))
            sleep(0.5)
            self.removed = 0
            self.deleted_plugins = {}
            return True
        self.__printMenu()


    # remove plugin menu
    def __pluginMenu(self):
        text = 'Enter plugin number ('
        if self.total_plugins > 1:
            text += '1-'+str(self.total_plugins)+'): '
        elif self.total_plugins == 1:
            text +='1): '
        else:
            print("There's no plugins !")
            sleep(1.0)
            self.__printMenu()
            return
        text += ' (Press Enter for main Menu): '
        pnum = input(text)
        if pnum.isdigit():
            if int(pnum) not in range(1,self.total_plugins+1):
                print('Invalid number: '+pnum)
                self.__pluginMenu()
            else:
                if not self.__removeplugin(pnum):
                    # print('ERROR')
                    self.__printError()
                self.__setAndResetAll()
                self.__createPluginsList()
                self.printAll()
                self.__pluginMenu()
        elif pnum == '':
            self.__printMenu()
        else:
            self.errormsg = 'Invalid selection. Type a number or Return'
            self.__printError()
            self.__pluginMenu()
     

    # file  write
    # params: filepath, filecontent
    def __fileWrite(self, f, c):
        # basic check but often not enough (on win at the least)
        if not os.access(os.path.dirname(f), os.W_OK):    
            self.writeerror = 'PermissionError'
            return False
        else:
            try:
                with open(f, 'w') as tfile:
                    try:
                        tfile.write(c)
                        return True
                    except (IOError, OSError) as ex:
                        self.writeerror = type(ex).__name__
            except (FileNotFoundError, PermissionError, OSError) as ex:
                self.writeerror = type(ex).__name__
            return False


    # save to a text file:
    def __saveToTextFile(self):
        fname = self.session_name+'.txt'
        rfile = os.path.join(os.path.dirname(os.path.abspath(self.afile)), fname)
        print(self.__formatString('Saving to: '+str(self.__noPath(rfile)), 105),end='')
        #file write
        data = content = 'Report created with '+self.name+' '+self.version+' - '+self.__today()+'\n'
        data += self.__prepareReport()
        if self.__fileWrite(rfile, data):    
            print(self.__colorize("Ok!", 'green'))
            return True
        else:
            print(self.__colorize("Failed!", 'red'))
            print(self.__colorize('['+self.writeerror+']', 'grey'))
        return False




# RUN
if __name__ == "__main__":
    sp = sessionParser()
