#!/usr/bin/env python

import sys, os, re, time, codecs, locale
from optparse import OptionParser
from os.path import *
from fnmatch import fnmatch

locale.setlocale(locale.LC_ALL, '')

def msg(text):
   if not options.quiet:
      print text

def create_dir(file):
   (updir, filename) = split(file)
   tmp = re.match("^(.+)\.[^.]+$", filename)
   if tmp is None:
      basedir = "dir-%s" % filename
   else:
      basedir = tmp.group(1)
   i = 0
   while True:
      if i == 0:
         dir = "%s/%s" % (updir, basedir)
      else:
         dir = "%s/%s.%d" % (updir, basedir, i)
      try:
         os.mkdir(dir)
         break
      except OSError:
         i += 1
   global dirlist
   dir = abspath(dir)
   dirlist.append(dir)
   return dir

def get_metavars():
   metavars = re.findall("%{\w+}", options.pattern)
   metavars = map(lambda x: x[2 : len(x) - 1], metavars)
   return metavars
   
def infer_metadata(file):
   metavars = get_metavars()
   metare = re.sub("%{\w+}", "([^/]+)", options.pattern)
   metare += '$'
   res = {}
   match = re.search(metare, file)
   if match is None:
      return None
   for index, name in zip(range(len(metavars)), metavars):
      value = match.group(index + 1)
      res[name] = value
   return res

def write_header(dir, meta, origfile):
   try:
      f = open("%s/header.xml" % dir, "w")
      print >> f, """<?xml version="1.0" encoding="UTF-8"?>
<cesHeader creator="dxces v1.0">
  <fileDesc>
    <titleStmt>
      <h.title>XCES-encoded version of "%s"</h.title>
    </titleStmt>
    <sourceDesc>
      <biblStruct>
        <monogr>""" % origfile
      if meta is not None:
         for key, value in meta.iteritems():
            print >> f, "          <%s>%s</%s>" % (key, value, key)
      print >> f, """        </monogr>
      </biblStruct>
    </sourceDesc>
  </fileDesc>
</cesHeader>"""
   except IOError:
      print >> sys.stderr, "Could not write header.xml for", origfile
   else:
      f.close()

repseudo = re.compile('\s+', re.U)
rewords = re.compile('([?!]+|\.+|-+|\W)', re.U)
rewhite = re.compile('^\s*$', re.U)

def write_paragraph(f, paragraph):
   pseudowords = repseudo.split(paragraph)
   # pseudowords are words 'from space to space', i.e. possibly with
   # interpunction characters
   prevword = ''
   # FIXME: add more shortcuts
   shortcuts = ['etc', 'itp', 'tzw', 'itd']
   for word in pseudowords:
      words = rewords.split(word)
      nospace = False
      for word in words:
         if rewhite.match(word):
            continue
         if options.struct and (re.match('[?!]+|\.+', prevword) 
         and prevword not in shortcuts) or prevword == '':
            if prevword != '':
               print >> f, "</chunk>"
            print >> f, '<chunk type="s">'
         if nospace:
            print >> f, '<ns/>'
         word = re.sub('&', '&amp;', word)
         word = re.sub('<', '&lt;', word)
         word = re.sub('"', '&quot;', word)
         print >> f, '<tok>'
         print >> f, '<orth>%s</orth>' % word
         tag = 'ign'
         if re.match('\W', word):
            tag = 'interp'
         print >> f, '<lex disamb="1"><base>dummy</base><ctag>%s</ctag></lex>' % tag
         print >> f, '</tok>'
         nospace = True
         prevword = word
   print >> f, '</chunk>'

def write_morph(dir, text, origfile):
   try:
      f = codecs.getwriter("utf-8")(open("%s/morph.xml" % dir, "w"))

      # write morph header
      print >> f, """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cesAna SYSTEM "xcesAnaIPI.dtd">
<cesAna xmlns:xlink="http://www.w3.org/1999/xlink" type="pre_morph" version="IPI-1.2">
<chunkList xml:base="text.xml">
<chunk type="wholedoc">"""

      # split the text into paragraphs
      paragraphs = re.split('([ \t\f\v\r]*[\n]){2,}[ \t\f\v]*', text)
      for paragraph in paragraphs:
         if rewhite.match(paragraph):
            continue
         if options.struct:
            print >> f, '<chunk type="p">'
         write_paragraph(f, paragraph)
         if options.struct:
            print >> f, '</chunk>'

      # write morph footer
      print >> f, "</chunk>\n</chunkList>\n</cesAna>"
   except IOError:
      print >> sys.stderr, "Could not write morph.xml for", origfile
   else:
      f.close()

def process_file(file):
   dispfile = basename(file)
   msg("Processing %s..." % dispfile)
   f = codecs.getreader(options.encoding)(open(file))
   dir = create_dir("%s/%s" % (options.name, dispfile))
   write_header(dir, infer_metadata(file), dispfile)
   text = f.read()
   f.close()
   write_morph(dir, text, dispfile)

def process(file):
   if isdir(file):
      for subfile in os.listdir(file):
         subfile = abspath("%s/%s" % (file, subfile))
         if isdir(subfile) or fnmatch(basename(subfile), options.path):
            process(subfile)
   else:
      try:
         process_file(file)
      except IOError:
         print >> sys.stderr, "Could not open file", file

def output_config():
   try:
      msg("Writing %s.cfg..." % options.name)
      f = open("%s/%s.cfg" % (options.name, options.name), "w")
      print >> f, """# Automatically generated by dxces

[ATTR]

# There are no attributes

[POS]

ign    =
interp =

[NAMED-ENTITY]

entity-orth = orth
entity-base = base
entity-tag = tag
entity-pos = pos
"""
      f.close()
      
      msg("writing %s.meta.cfg..." % options.name)
      msg("writing %s.meta.lisp..." % options.name)
      f = open("%s/%s.meta.cfg" % (options.name, options.name), "w")
      g = open("%s/%s.meta.lisp" % (options.name, options.name), "w")
      print >> g, ";;; Automatically generated by dxces"
      for meta in get_metavars():
         print >> f, "S %s" % meta
         print >> g, '(single "%s" "/cesHeader/fileDesc/sourceDesc/biblStruct/monogr/%s")' % (meta, meta)
      f.close()
      g.close()
   except IOError:
      print >> sys.stderr, "Failed to write configuration files"
      sys.exit(1)

usage = "%prog [OPTIONS] DIRECTORIES-OR-FILES..."
parser = OptionParser(usage = usage, version = "dxces.py 1.0")
parser.add_option("-n", "--base-name", help = "set the basename of resulting "
   "corpus", dest = "name", default = "corpus")
parser.add_option("-e", "--encoding", help = "specify encoding of source "
   "files (default: %default)", dest = "encoding", default = "utf-8")
parser.add_option("-q", "--quiet", help = "suppress output",
   action = "store_true", dest = "quiet", default = False)
parser.add_option("-s", "--no-structure", help = "inhibit structural markup "
   "detection heuristics", action = "store_false", dest = "struct",
   default = True)
parser.add_option("-r", "--remove-xces", help = "remove XCES files after "
   "building the binary corpus", action = "store_true", dest = "remove",
   default = False)
parser.add_option("-p", "--path", help = "scan directories looking for "
   "files whose names match the specified pattern (default: %default)",
   dest = "path", default = "*.txt")
parser.add_option("-m", "--metadata-pattern", help = "use the specified pattern "
   "to try to determine document metadata from pathnames (default: "
   "%default)", dest = "pattern", default = "%{author}/%{title}.txt")
parser.add_option("-b", "--no-build", help = "don't build the binary corpus "
   "with bp (default when bp is not found in PATH, implies -i)", 
   action = "store_false", dest = "build", default = True)
parser.add_option("--bp-opts", help = "pass the given options to bp",
   dest = "bpopts", metavar = "OPTS", default = "")
parser.add_option("-i", "--no-index", help = "don't index the binary corpus "
   "after building it (default when indexer is not found in PATH)", 
   action = "store_false", dest = "index", default = True)
parser.add_option("--indexer-opts", help = "pass the given options to indexer",
   dest = "indexeropts", metavar = "OPTS", default = "")

(options, args) = parser.parse_args()
if len(args) == 0:
   parser.print_help()
   sys.exit()
dirlist = []
try:
   os.mkdir(options.name)
except OSError:
   print >> sys.stderr, "Warning: directory %s already exists" % options.name
for file in args:
   process(abspath(file))
output_config()
if options.build:
   try:
      msg("Building corpus...")
      os.chdir(options.name)
      os.system("bp %s %s" % (options.bpopts, options.name))
      if options.index:
         try:
            msg("Indexing corpus...")
            os.system("indexer %s %s" % (options.bpopts, options.name))
         except OSError:
            print >> sys.stderr, "Unable to invoke indexer."
      os.chdir('..')
   except OSError:
      print >> sys.stderr, "Unable to invoke bp."
if options.remove:
   try:
      for dir in dirlist:
         for file in os.listdir(dir):
            os.remove("%s/%s" % (dir, file))
         os.rmdir(dir)
   except OSError:
      print >> sys.stderr, "Unable to remove XCES files."

