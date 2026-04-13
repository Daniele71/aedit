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

# extend dict
# add or extend values
# use lists for storing values
class mdict(dict):

    def __init__(self):
        super().__init__()
        self.total = 0
    # add or extend
    def add(self, key, val):
        if key in self:
            self[key].extend([(val)])
        else:
            self[key] = [(val)]
        self.total += 1


# CLASS
class sessionParser():
    def __init__(self):
        # vars
        self.name = 'aedit'
        self.version = '2.0.0'
        self.export_format = 'html' # or text
        self.plugins_type = ('vst2', 'vst3', 'luaproc', 'clap', 'lv2', 'lxvst')
        self.__setAndResetAll()
        self.removed = 0
        self.deleted_plugins = mdict() # track -> plugin name
        self.afile = None
        self.nn = 1 # counter for html report for id generation
        self.snn = 0 # counter for how many sessions are in the report also sesson number
        self.sessions_list = {}
        self.sessions_failed = {}
        self.sessions_skipped = {}
        # keep for now, require for single file report
        self.parsed_count = 0
        self.parsed_error = 0
        self.parsed_skipped = 0
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
        self.aparser.add_argument("-text", action='store_true', help="Export in plain text format")
        self.aparser.add_argument("-verbose", action='store_true', help="List ALL takes with fx, they could be thousands of lines !!!!")
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
            self.afile = None
            self.__mainMenu()
        # parse session file
        if not self.__parseArdourFile(self.afile):
            self.__printError()
            return
        self.wdir = os.path.dirname(self.afile)
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
            return
            # sys.exit()
        path = os.path.abspath(self.wdir)
        if not os.access(path, os.W_OK):
            print('Session path not readable')
            syx.exit()
        print('\nSessions Dir: ', self.__noPath(path), '\n')
        # counters
        self.parsed_count = 0
        self.parsed_error = 0
        self.parsed_skipped = 0
        for d in sorted(os.listdir(path)):
            # if self.parsed_count == 5:
            #     continue
            if os.path.isdir(os.path.join(path, d)):
                if os.path.isfile(os.path.join(path, d, d+'.ardour')):
                    fname = d+'.ardour'
                    self.afile = os.path.join(path, d, d+'.ardour')
                    print(self.__formatString('Parsing: '+self.__noPath(self.afile), 120), end='')
                    if self.__parseArdourFile(self.afile):
                        self.__createPluginsList()
                        self.parsed_count +=1
                        self.sessions_list[self.parsed_count] = self.session_name
                        # print(self.session_name)
                        ###
                        self.num = 0
                        # single file
                        if self.args.save:
                            content += self.__prepareReport()
                            print(self.__colorize('Ok!', 'green'))
                            self.__setAndResetAll()
                        else:
                            print(self.__colorize('Ok!', 'green'))
                            if not self.__saveToTextFile():
                                self.parsed_error +=1
                            self.__setAndResetAll()
                            print('')
                    else:
                        # wrong *.ardour file
                        print(self.__colorize('Skipped!', 'orange'))
                        print(self.__colorize('['+self.errormsg+']', 'grey'))
                        self.sessions_skipped[os.path.join(d, self.__noPath(self.afile, True))] = self.errormsg
                        self.parsed_skipped += 1
                        sleep(0.5)
                        print('')
                else:   
                    # print('Error : ', os.path.join(path, d, d+'.ardour'))
                    print(self.__formatString('\nParsing: '+self.__colorize(self.__noPath(os.path.join(path, d, d+'.ardour')), 'grey'), 130), end='')
                    print(self.__colorize('Failed!', 'red'))
                    print(self.__colorize('[Missing/Invalid file]', 'grey'), '\n')
                    self.sessions_failed[os.path.join(d, d+'.ardour')] = 'Missing/Invalid file'
                    self.parsed_error +=1
                    sleep(0.8)
        # how faster are we ?
        # we add 0.03  'cause file write happens later ;)
        tend = "%.3fs" % (time() - (tstart+0.02))
        print('\nCompleted!', self.__colorize('('+tend+')', 'grey'))
        if content:
            #print('Saving full report\n')
            self.__writeReport(path, content)
            # print(self.sessions_list)
        else:
            print(self.__scanResults())
        # print(self.sessions_list)
        # clean up
        self.__setAndResetAll()
        self.removed = 0
        self.deleted_plugins = {}
        self.afile = False

    # scan results
    def __scanResults(self):
        res = 'Parsed Sessions: '+str(self.parsed_count)+'  Good: '+ str(self.parsed_count-self.parsed_error)+'  Error: '+ str(self.parsed_error)+ '  Skipped: '+ str(self.parsed_skipped)+ '\n'
        return res + '-'*115+'\n'

    # text header
    def __textReportHeader(self):
        content = 'Report created with '+self.name+' '+self.version+' - '+self.__today()+'\n'
        content += 'Session dir: '+self.__noPath(self.wdir)+'\n'
        return content

    ## write single report
    def __writeReport(self, path, data):
        if self.args.text:
            fext = '.txt'
            content = self.__textReportHeader()
            content += self.__scanResults()+data
        else:
            fext = '.html'
            content = self.__htmlPage(data)
        fname = 'sessions_report'+fext
        rfile = os.path.join(path, fname)
        print(self.__scanResults())
        print(self.__formatString('\nSaving report to: '+str(self.__noPath(rfile)), 121), end='')
        # return
        if self.__fileWrite(rfile, content):
            sleep(0.4)
            print(self.__colorize("Ok!", 'green'))
            sleep(0.4)
        else:
            print(self.__colorize("Failed!", 'red'))
            print(self.__colorize('['+self.writeerror+']', 'grey'))

    # save to a text file:
    def __saveToTextFile(self):
        if self.args.text:
            fext = '.txt'
            content = self.__textReportHeader()
            content += self.__prepareReport()
        else:
            fext = '.html'
            content = self.__htmlPage(self.__prepareReport(), True)
        fname = self.session_name+fext
        rfile = os.path.join(os.path.dirname(os.path.abspath(self.afile)), fname)
        print(self.__formatString('Saving to: '+str(self.__noPath(rfile)), 120),end='')
        #file write
        if self.__fileWrite(rfile, content):
            print(self.__colorize("Ok!", 'green'))
            return True
        else:
            print(self.__colorize("Failed!", 'red'))
            print(self.__colorize('['+self.writeerror+']', 'grey'))
        return False


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
        ls = self.plugins_store[num]
        for child in self.eroot:
            if ls[0][3] == 'plugins':
                # print('delete plugin')
                # tracks
                for tr in child.findall('Route'):
                    for pr in tr.findall('Processor'):
                        # plugins
                        if pr.attrib['type'] in self.plugins_type:
                            # remove plugin with this id
                            if pr.attrib['id'] == ls[0][0]:
                                tr.remove(pr)
                                return self.__removePluginResult(num, tr.attrib['name'], pr.attrib['name'], pr.attrib['type'])
                # print('GFX remover')
                for ee in child.findall('Playlist'):
                    for pr in ee.findall('Region'):
                        # all regions
                        #do we have fx ?
                        fx = len(pr.findall('RegionFXPlugin'))
                        if fx > 0:
                            for aa in pr.findall('RegionFXPlugin'):
                                if ls[0][0] == aa.attrib['id']:
                                    pr.remove(aa)
                                    return self.__removePluginResult(num, pr.attrib['name'], aa.attrib['name'], aa.attrib['type'])
        self.errormsg = 'REMOVE ERROR'
            # return True


    # remove plugin result
    def __removePluginResult(self, num, tname, pname, ptype):
        print(self.__formatString('\nPlugin n.'+str(num)+' "'+pname+'": ', 80), end='')
        sleep(0.3)
        self.removed += 1
        # self.__addRemovedPlugin(tname, pname, ptype)
        self.deleted_plugins.add(tname, (pname, ptype))
        print(self.__colorize("Removed!", 'green'))
        sleep(0.5)
        return True

    # create plugins list
    def __createPluginsList(self):
        for child in self.eroot:
            for ee in child.findall('Route'):
                self.tracks.add(ee.attrib['id'] , (ee.attrib['name'], ee.attrib['default-type']))
                for pr in ee.findall('Processor'):
                    if pr.attrib['type'] in self.plugins_type:
                        self.__pluginCount(pr.attrib['type'])
                        self.num += 1
                        self.plugins_list.add(ee.attrib['id'], (pr.attrib['id'], pr.attrib['name'], pr.attrib['type']))
            # regions and regions plugins
            for ee in child.findall('Playlist'):
                for pr in ee.findall('Region'):
                    # all regions
                    self.regions.add(ee.attrib['orig-track-id'],(pr.attrib['name']))
                    #do we have fx ?
                    fx = len(pr.findall('RegionFXPlugin'))
                    if fx > 0:
                        for aa in pr.findall('RegionFXPlugin'):
                            self.gfx.add(pr.attrib['name'], (aa.attrib['id'], aa.attrib['name'], aa.attrib['type']))
                            self.__pluginCount(aa.attrib['type'])
                        # region with fx
                        self.regions_fx.add(ee.attrib['orig-track-id'],(pr.attrib['name']))

    # counte plugin by type
    def __pluginCount(self, pt):
        if pt in self.ptype:
            self.ptype[pt] += 1

    # total plugins
    def __totalPlugins(self):
        total = 0
        for k in self.ptype:
            total += self.ptype[k]
        return total

    # set/reset all vars before (re)scan
    def __setAndResetAll(self):
        #print('RESETTING')
        self.num = 0 # for display and for deletion
        self.plugins_store = mdict()
        self.plugins_list = mdict() # plugin list for each track
        self.tracks = mdict()
        self.regions = mdict()
        self.regions_fx = mdict()
        self.gfx = mdict()
        self.ptype = {}
        self.ptype['lv2'] = 0
        self.ptype['vst2'] = 0
        self.ptype['vst3'] = 0
        self.ptype['lxvst'] = 0
        self.ptype['luaproc'] = 0
        self.ptype['clap'] = 0

    # print error message
    # and wait a bit
    def __printError(self):
        print(self.__colorize(self.__boldfier('# ERRROR ! : '), 'red')+self.errormsg)
        sleep(0.5)


    # format string
    def __formatString(self, st1, nn):
        return f"{st1:<{nn}}"


    # prepare info text
    # screen and text
    def __infoText(self, nopath = False):
        recapinfo = self.__boldfier('\nINFO:\n')
        recapinfo += self.__formatString(' Session:', 20)+self.session_name+'\n'
        recapinfo += self.__formatString(' Version:', 20)+self.session_version+'\n'
        recapinfo += self.__formatString(' Sample Rate:', 20)+str(self.session_sr)+" hz\n"
        recapinfo += self.__formatString(' Tracks:', 20)+str(self.tracks.total)+"\n"
        recapinfo += self.__formatString(' Ragions:', 20)+str(self.regions.total)+"\n"
        recapinfo += self.__formatString(" Created with:", 20)+self.created_with+'\n'
        recapinfo += self.__formatString(" Modified with:", 20)+self.modified_with+'\n'
        recapinfo += self.__formatString(' Session file:', 20)+self.__noPath(self.afile, nopath)+'\n'
        recapinfo += '-'*115
        return recapinfo


    # recap plugins
    # screen and text
    def __recapText(self):
        recaptext = self.__formatString(self.__boldfier('\nPLUGINS:'), 30)+str(self.__totalPlugins())+'\n'
        recaptext += self.__formatString(' lv2:', 12)+self.__formatString(str(self.ptype['lv2']), 8)+self.__formatString('vst2:', 12)+str(self.ptype['vst2'])+'\n'
        recaptext += self.__formatString(' vst3:', 12)+self.__formatString(str(self.ptype['vst3']),8)+self.__formatString('lxvst:', 12)+str(self.ptype['lxvst'])+'\n'
        recaptext += self.__formatString(' lua:', 12)+self.__formatString(str(self.ptype['luaproc']),8)+self.__formatString('clap:', 12)+str(self.ptype['clap'])+'\n'
        recaptext += '-'*115
        return recaptext


    # prepare plugin list
    # screen and text
    # nonum True to avoid numbering while exporting text report
    def __pluginText(self, nonum = False):
        # print(self.plugins_list)
        # print(self.regions)
        self.num = 1
        pltext = self.__boldfier('\nTRACK/PLUGIN/REGIONS:\n')
        for k in self.tracks:
            regl = ''
            if k in self.regions:
                regl = ' | '+self.__colorize('Regions: '+str(len(self.regions[k])), 'grey')
            for v in self.tracks[k]:
                pltext += self.__boldfier('\n\n'+self.__colorize(v[0], 'blue'))
                pltext += regl
                pltext += ' | '+self.__colorize(v[1], 'grey')+'\n'
                if k in self.plugins_list:
                    for e in self.plugins_list[k]:
                        # add id, name, type, plugins/gfx
                        self.plugins_store.add(self.num, (e[0], e[1], e[2], 'plugins'))
                        if nonum:
                            num = '  ';
                        else:
                            num = self.__formatString(' '+str(self.num)+')', 7)
                        pltext += self.__formatString(num+e[1], 110)+e[2]+'\n'
                        self.num += 1
            # verbose output ?
            if self.args.verbose:
                rg = self.regions
                rtext = ':'
            else:
                rg = self.regions_fx
                rtext = ' with plugins:'
            for a in rg:
                # print(a, k)
                if k == a:
                    pltext += self.__colorize(' REGIONS'+rtext, 'green')+'\n'
                    for t in rg[a]:
                        pltext += '  '+self.__colorize(str(t), 'red')+'\n'
                        # data += '   Take: '+t+'\n'
                        if t in self.gfx:
                            for g in self.gfx[t]:
                                self.plugins_store.add(self.num,(g[0], g[1], g[2], 'gfx'))
                                if nonum:
                                    num = '  ';
                                else:
                                    num = self.__formatString(' '+str(self.num)+')', 7)
                                pltext += self.__formatString(num+g[1], 110)+g[2]+'\n'
                                self.num += 1
        pltext += '-'*115+'\n'
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
    # disable numbering when saving to file
    def __prepareReport(self):
        if self.args.text:
            report = self.__infoText(True)
            report += '\n'+self.__recapText()
            report += '\n'+self.__pluginText(True)+'\n\n'
            return self.__removeANSI(report)
        else:
            return self.__prepareHtmlReport()

    # print results
    def printAll(self):
        print(self.__infoText())
        print(self.__recapText())
        print(self.__pluginText())


    # print menu
    def __printMenu(self):
        menu = '\n'+self.__boldfier('\033[04mEDIT ACTIONS:\033[0m\n')
        if self.deleted_plugins:
            menu += "w) re-Write session file"
            menu += self.__colorize(' (!)', 'grey')+'\n'
            menu += "v) View changes"+self.__colorize(" ("+str(self.removed)+')', 'grey')+'\n'
        else:
             menu += self.__colorize("w) re-Write session file", 'grey')+'\n'
             menu += self.__colorize("v) View changes", 'grey')+'\n'
        #menu += '\n'
        menu += "s) Save text report "+self.__colorize('(.txt)', 'grey')+"\n"
        menu += "h) Save html report "+self.__colorize('(.html)', 'grey')+"\n"
        if self.__totalPlugins() == 0:
            menu += self.__colorize("r) Remove plugin\n", 'grey')
        else:
             menu += "r) Remove plugin\n"
        menu += "m) Main Menu\n"
        menu += "q) Quit\n"
        print(menu)
        sel = input("Enter option: ")
        if sel == 's':
            self.args.html = False
            self.__saveToTextFile()
            sleep(0.5)
        elif sel == 'h':
            self.args.html = True
            self.__saveToTextFile()
            sleep(0.5)
            sys.exit()
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
        if self.deleted_plugins:
            print('\n')
            print(self.__boldfier('\033[04mREMOVED PLUGINS:\033[0m\n'))
            for k in self.deleted_plugins:
                print(self.__formatString(self.__colorize(k+':', 'blue'), 56))
                for v in self.deleted_plugins[k]:
                    print('- ', v[0], self.__colorize(v[1], 'grey'))
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
        menu += "s) Sessions Report\n"
        # loaded file ?
        if not self.afile:
            menu += self.__colorize("e) Edit Ardour file\n", 'grey')
        else:
            menu += "e) Edit Ardour file "+self.__colorize('('+self.__noPath(self.afile, True), 'grey')+")\n"
        # check nopath
        if not self.args.nopath:
            np = '(Off)'
        else:
            np = '(On)'
        menu += 'n) set/unset nopath '+self.__colorize(np, 'grey')+'\n'
        if not self.args.verbose:
            vb = '(Off)'
        else:
            vb = '(On)'
        menu += 'v) set/unset verbose '+self.__colorize(vb, 'grey')+'\n'
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
            self.__sessionReportMenu()
        elif sel == 'n':
            self.args.nopath = not self.args.nopath
        elif sel == 'v':
            self.args.verbose = not self.args.verbose
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

    
    # session report menu
    def __sessionReportMenu(self):
        menu = '\n'+self.__boldfier('\033[04mSESSIONS REPORT:\033[0m\n')
        menu += "c) Change export format txt / html "+self.__colorize('('+self.export_format+')', 'grey')+'\n'
        menu += 's) Single file \n'
        menu += 'm) Multiple files\n'
        print(menu)
        sel = input("Enter option (or pres return for main menu): ")
        sel = str(sel).lower()
        if sel == '':
            self.__mainMenu()
        elif sel == 'c':
            self.__formatMenu()
        elif sel == 's':
            # add check here
            o = input('Sessions Dir: ')
            self.args.dir = o
            if not str(o).lower() == '':
                self.args.save = True
                self.__parseSessionsDir()
            else:
                self.errormsg = "Invalid Option"
                self.__printError()
            # single file
        elif sel == 'm':
            # multiple files
            o = input('Sessions Dir: ')
            if not str(o).lower() == '':
                self.args.dir = o
                self.args.save = False
                self.__parseSessionsDir()
            else:
                self.errormsg = "Invalid Option"
                self.__printError()
        else:
            self.errormsg = "Invalid Option"
            self.__printError()
            self.__sessionReportMenu()
        self.__mainMenu()

    # format menu
    def __formatMenu(self):
        menu = '\n'+self.__boldfier('\033[04mEXPORT FORMAT:\033[0m\n')
        menu += 't) Text\n'
        menu += 'h) Html\n'
        print(menu)
        o = input('Select format or press enter: ')
        sel = str(o).lower()
        if sel == '':
            self.__sessionReportMenu()
        elif sel == 't':
            print('Export format: text')
            self.export_format = 'txt'
            self.args.html = False
            # set text
        elif sel == 'h':
            print('Export format: html')
            self.export_format = 'html'
            self.args.html = True
            #set html
        else:
            self.errormsg = 'Invalid option'
            self.__printError()
            self.__formatMenu()
        self.__sessionReportMenu()

    # print some info
    def __sysInfoText(self):
        text = '\n'+self.__boldfier('\033[04mSYSTEM INFO:\033[0m\n')
        text += 'Program: '+self.name+' - '+self.version+'\n'
        text += 'Platform: '+sys.platform+'\n'
        text += 'Pyhton: '+str(sys.version_info.major)+'.'+str(sys.version_info.major)+'.'+str(sys.version_info.micro)+'\n'
        text += 'Project page: https://github.com/Daniele71/aedit\n'
        text += 'Ardour: https://ardour.org/\n'
        text += '-'*50
        return text


    # confirm exit, if needed
    def __confirmExit(self):
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
            self.deleted_plugins = mdict()
            return True
        self.__printMenu()


    # remove plugin menu
    def __pluginMenu(self):
        text = 'Enter plugin number ('
        if self.__totalPlugins() > 1:
            text += '1-'+str(self.__totalPlugins())+'): '
        elif self.totalPlugins() == 1:
            text +='1): '
        else:
            print("There's no plugins !")
            sleep(1.0)
            self.__printMenu()
            return
        text += ' (Press Enter for main Menu): '
        pnum = input(text)
        if pnum.isdigit():
            if int(pnum) not in range(1,self.__totalPlugins()+1):
                print('Invalid number: '+pnum)
                self.__pluginMenu()
            else:
                if not self.__removeplugin(pnum):
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


    ################ html #################
    # full html page
    # r = True - remove counter for single report
    def __htmlPage(self, body, r = False):
        if self.args.save:
            tl = self.session_name+' report'
        if self.args.dir and self.args.save:
            tl = 'Sessions report'
            ses = "<p>Session dir: "+self.__noPath(self.wdir)+"</p>"
        else:
            ses = "<p>File: "+self.__noPath(self.afile, True)+"</p>"
            tl = self.session_name+' report'
        errors = self.__errorsHtml()
        page = """\
        <!doctype html>
        <head>
        <meta charset='utf-8'>
        <title>{}</title>
            <style>
            body {{
            min-height: 100vh;
            margin: auto;
            background-color: grey;
            width: 960px;
            }}
            p {{
                padding:2px;
                margin: 0;
            }}
            .mybox {{
                display: block;
                background-color: #3d3d3a;
                color: white;
                font-weight: bold;
                padding: 10px 8px 10px 8px;
                border-radius: 8px;
                border: thin dashed white;
                margin: 8px 60px 8px 60px;
            }}
            .container {{
                background-color: #f2f2f2;
                display: block;
                padding: 4px;
                margin: 10px 60px 10px 60px;
                border-radius: 8px;
                border: thin solid black;
            }}
            .su {{
                text-align: center;
                display: block;
                margin: 6px 60px 6px 60px;
                font-weight: bold;
            }}
            .sep {{
                padding-bottom: 8px;
                border-bottom: thin dashed grey;
                margin-bottom: 10px;
                margin-top: 2px;
            }}
            .sep_noborder {{
                padding-bottom: 6px;
                margin-bottom: 5px;
                # margin-top: 2px;
            }}
            th {{
                text-align: left;
                padding: 3px 10px 3px 12px;
                color: white;
                background-color: #3d3d3a;
            }}
            .th1 {{
				text-align: left;
                padding: 3px 2px 3px 4px;
                color: white;
				width: 758px;
			}}
            .tdi {{
                padding-right: 40px;
            }}
            .tda {{
                padding-right: 60px;
            }}
            .tdb {{
                padding-left: 50px;
                padding-right: 50px;
            }}
            .tdp {{
                padding: 0 5px 0 4px;
                 width: 754px;
            }}
            .tks {{
                color: #b40000;
                padding-left: 8px;
                font-weight: bold;
            }}
            .tkp {{
                padding-left: 38px
            }}
            .tts {{
                font-weight: bold;
                padding-left: 2px;
                color: #006d00;
            }}
            .ttt {{
                font-weight: bold;
                color: #3d3d3a;
            }}
            .tx {{
                padding-left: 16px;
                width: 744px;
            }}
            .d {{
                margin: 0;
                padding: 0;
                display: none;
            }}
            .title {{
                text-align: left;
                font-weight: bold;
                color: #cc0000;
            }}
             .titleb {{
                padding: 4px 0 8px 0;
                font-size: 160%;
                color: green;
            }}
            .bb {{
                padding: 40px 1px 8px 0;
                font-size: 160%;
                color: grey;
            }}

            a {{
                color: #a8a5a5;
                text-decoration: none;
            }}
            a:hover {{
                color: white;
            }}
            a.reg {{
                text-decoration: none;
            }}
            a.reg:hover {{
                color: #ffcb62;
                text-decoration: none;
            }}
            a.nav {{
                color: #d0d0d0;
            }}
             a.nav:hover {{
                color: white;
            }}
             .pdet {{
                color: #3d3d3a;
            }}
            #nav {{
                margin-top: 10px;
            }}
            .dtest {{
                border: 2px dashed red;
                padding:0;
            }}
            .track {{
                color: white;
            }}
            a.track:hover {{
                color: #23FC17;
            }}
            .thtrack {{
                cursor: pointer;
            }}
            .thtrack:hover {{
                color: #23FC17;
            }}
             .threg {{
                cursor: pointer;
                color: #b3b3b3;;
            }}
            .threg:hover {{
                color: #fff895;

            }}
            table {{
                margin:0;
            }}
            .tplug, .treg, .ttrack {{
                width: 100%;
                border-bottom: 1px dashed #d4d4d4;
            }}
            .white {{
                color: white;
            }}
            </style>
            <script>
            function Show(id){{
                console.log(arguments)
                if (arguments[1]){{
                    Show(arguments[1]);
                }}
                if (document.getElementById(id)){{
                    var tr = document.getElementById(id);
                    if(tr.style.display == "none"){{
                    tr.style.display = "block";
                    }}else{{
                    tr.style.display = "none";
                    }}
                }}
                }}

            function ExpandAll(){{
                event.preventDefault();
                const el = document.querySelector("#exbt")
                 if (el.innerText == "Show") {{
                        el.innerText = "Hide";
                        var ds = "block";
                }} else {{
                        el.innerText = "Show";
                        var ds = "none";
                }}
                var x = document.querySelectorAll(".d");
                var i;
                for (i = 0; i < x.length; i++) {{
                x[i].style.display = ds;
                }}
            }}

            function GotoSession(){{
                var ss = document.navform.sel.value;
                if (!ss){{
                event.preventDefault();
                return false;
                }}
                var go = '#session'+ss;
                window.location.href = go;
            }}
        </script>
        </head>
            <body>
                <div class='mybox'>
                    <p>Report created with {}-{}  {}</p>
                    {}
                    REMOVE<p>Parsed Sessions: {}  Good:<span style='color: #00ff00'> {}</span> Error: <span style='color:#ff0000'>{}</span> Skipped:<span style='color: #ffaa00'> {}</span>{}
                </div>
                {}
                 <!--  errors section -->
                {}
                <div class='mybox'>
                Ardour: <a href="https://ardour.org">https://ardour.org/</a><br />
                aedit: <a href="https://github.com/Daniele71/aedit">https://github.com/Daniele71/aedit</a>
                </div>
            </body>
        </html>
        """.format(tl, self.name, self.version, self.__today(), ses, self.parsed_count, self.parsed_count-self.parsed_error, self.parsed_error, self.parsed_skipped, self.__navForm(), body, errors)
        if r:
            return re.sub(r'REMOVE.*\n?', '', page)
        else:
            return page.replace('REMOVE', '')

    # wrap failed and skipped sessions
    # avoid for single file report
    def __errorsHtml(self):
        if len(self.sessions_failed) + len(self.sessions_skipped) == 0 or not self.args.save:
            return ''
        failed = self.__htmlFailed() if len(self.sessions_failed) > 0 else ''
        skipped = self.__htmlSkipped() if len(self.sessions_skipped) > 0 else ''
        body ="""\
            <!-- container  -->
            <div class='container'>
                <!-- failed  -->
                {}
                <!-- skipped  -->
                {}
            </div>
            <!--  end container -->
            """.format(failed, skipped)
        return body

    # failed sessions
    def __htmlFailed(self):
        tb = "<table>"
        for k in self.sessions_failed:
            tb += "<tr><td>"+k+"</td></tr>"
            tb += "<tr><td  style='color: grey;'>"+self.sessions_failed[k]+"</td></tr>"
        tb += "</table>\n"
        body="""\
                <div class="sep">
                 <div class="title" id='sessionfailed'>Failed</div>
                {}
                </div>
            """.format(tb)
        return body

    # skipped sessions
    def __htmlSkipped(self):
        tb = "<table>"
        for k in self.sessions_skipped:
            tb += "<tr><td>"+k+"</td></tr>"
            tb += "<tr><td style='color: grey;'>"+self.sessions_skipped[k]+"</td></tr>"
        tb += "</table>\n"
        body="""\
                <div class="sep_noborder">
                 <div style='color:#ec9d00;' id='sessionskipped'>Skipped</div>
                {}
                </div>
            """.format(tb)
        return body

    # prepare the html body
    def __prepareHtmlReport(self):
        self.snn +=1
        goup = "<div title='Back to top' class='su'><a class='nav' href='#'>: :: Top :: :</a></div>"
        body = """\
            <!-- container  -->
            <div class='container'>
                <div class="sep">
                {}
                </div>
                <div class='sep'>
                {}
                </div>
                <div class="title">TRACKS / PLUGINS / REGIONS / FX</div>
                {}
            </div>
            <!--  end container -->
            NAVIGATION
            """.format(self.__infoHtml(), self.__recapHtml(), self.__pluginsHtml())
        return body.replace('NAVIGATION', goup)

    # infoHtml
    # force nopath for file name
    def __infoHtml(self):
        nm = 'session'+str(self.snn)
        nn = "<b class='bb'>"+str(self.snn)+') </b>'
        if not self.args.dir or not self.args.save:
            nn = ''
        session_info = """\
        <table>
            <tr><td class='tdi' colspan='2'>{}<b id='{}' class='titleb'>{}</b></td></tr>
            <tr><td class='tdi'>Version:</td><td>{}</td></tr>
            <tr><td class='tdi'>Sample Rate:</td><td>{} Hz</td></tr>
            <tr><td class='tdi'>Tracks:</td><td>{}</td></tr>
            <tr><td class='tdi'>Regions:</td><td>{}</td></tr>
            <tr><td class='tdi'>Created with:</td><td>{}</td></tr>
            <tr><td class='tdi'>Modified with:</td><td>{}</td></tr>
            <tr><td class='tdi'>File name:</td><td>{}</td></tr>
        </table>
        """.format(nn, nm, self.session_name, self.session_version, self.session_sr, self.tracks.total, self.regions.total, self.created_with, self.modified_with, self.__noPath(self.afile, True))
        return session_info

    # navigation form
    # TODO: remove self.reion_counter ?
    def __navForm(self):
        fm = "\n\t<form name='navform' id='nav'>"
        if self.args.dir and self.args.save:
            fm += "Session: <select name='sel' id='sel' onclick='GotoSession()'>\n<option value='' style='color: grey;'>Select session...</option>\n"
            for k in self.sessions_list:
                ss = self.sessions_list[k]
                if len(self.sessions_list[k]) > 40:
                    ss = self.sessions_list[k][0:40]+'...'
                fm += "\t<option value='"+str(k)+"'>"+ss+"</option>\n"
            if len(self.sessions_failed) > 0:
                fm +="<option style='color: red;' value='failed'>Failed</option>"
            else:
                fm +="<option style='color: #e6b3a7;' disabled>Failed</option>"
            if len(self.sessions_skipped) > 0:
                fm +="<option style='color: #ec9d00;' value='skipped'>Skipped</option>"
            else:
                fm +="<option style='color: #ecc685' disabled>Skipped</option>"
            fm +="</select>\n"
        fm += "Show All ! <button id='exbt' title='Expand all to see plugins and regions !' onclick='ExpandAll()'>Show</button></form>\n"
        return fm

    # recap plugins
    def __recapHtml(self):
        plugins = """\
        <div class="title">PLUGINS: {} <span class='pdet'> ({} on tracks - {} on regions)</span> </div>
        <table>
            <tr><td class='tda'>lv2</td><td>{}</td><td class='tdb'>vst</td><td>{}</td><td class='tdb'>vst3</td><td class='tdb'>{}</td></tr>
            <tr><td class='tda'>lxvst</td><td>{}</td><td class='tdb'>clap</td><td>{}</td><td class='tdb'>lua</td><td class='tdb'>{}</td></tr>
        </table>
        """.format(self.__totalPlugins(),  self.plugins_list.total, self.gfx.total, self.ptype['lv2'], self.ptype['vst2'], self.ptype['vst3'], self.ptype['lxvst'], self.ptype['clap'], self.ptype['luaproc'])
        return plugins


    # plugins list for html report
    # TODO: remove verbose ?
    def __pluginsHtml(self):
        gnum = 0;
        pltext = '<!-- open main table --><table>\n'
        for k in self.tracks:
            regl = ''
            idn = ''
            if k in self.regions:
                idn = str(self.nn)+'d'
                regl = " : <span name='"+'reg'+str(self.nn)+"' class='threg' onclick='Show(\""+idn+"\")'>Regions: <span class='white'>"+str(len(self.regions[k]))+"</span> Fx: <span class='white'>#fx#</span></span>"
            for v in self.tracks[k]:
                # track
                pltext += """\
                \n<tr rowspan='2'><th class='th1'><span class='thtrack' onclick='Show("{}test","{}")'>{}</span><br />#pl#{}</th><th>{}</th></tr>
                """.format(self.nn, idn, v[0], regl, v[1])
                if k in self.plugins_list:
                    pltext += "<tr><td colspan=2><div class='d' id='"+str(self.nn)+"test' style='display: none;'><!-- open plugins table --><table class='tplug'>"
                    pltext = pltext.replace('#pl#',"<span onclick='Show(\""+str(self.nn)+"test"+"\")' class='threg'>Plugins: <span class='white'>"+str(len(self.plugins_list[k]))+"</span></span>")
                    # plugin
                    for e in self.plugins_list[k]:
                        # add id, name, type, plugins/gfx
                        pltext += """\
                        <tr><td class='tdp'>{}</td><td>{}</td></tr>
                        """.format(e[1], e[2])
                    pltext += "<!-- close plugins table --></table></td></tr>\n"
                else:
                    pltext = pltext.replace('#pl#','')
                gnum = 0;
                for a in self.regions:
                    if k == a:
                        pltext += "\t<tr><td colspan='2'><div class='d' id='"+idn+"' style='display: none;'><!-- open regions table --><table class='treg'>\n"
                        for t in self.regions[a]:
                            pltext += "\t<tr><td colspan='2' class='tks'>"+t+"</td></tr>\n"
                            if t in self.gfx:
                                for g in self.gfx[t]:
                                    pltext +="<tr><td class='tx'>{}</td><td>{}</td></tr>\n".format(g[1],g[2])
                                    gnum += 1
                        pltext += "</table><!-- close regions table --></div></td></tr>\n"
                        pltext = pltext.replace('#fx#', str(gnum))
                self.nn +=1
        pltext += '</table><!-- close main table-->\n'
        return pltext

# RUN
if __name__ == "__main__":
    sp = sessionParser()
