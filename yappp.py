#!/usr/bin/python

from argparse import ArgumentParser
from struct import *
import zlib
import sys
import json

#
# Print error message
def perror(msg):
    sys.stderr.write('[x] %s\n' % msg)
    sys.stderr.flush()


#
# Verify PNG magic signature
def verifysignature(indata):
    return indata[:8] == '\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'


#
# Parse PNG chunks
def parsechunks(indata, outdata):
    outdata['chunks'] = {}

    cur = 8
    while cur < len(indata):

        # grab length and type
        chunk_len = unpack('>I', indata[cur:cur+4])[0]
        chunk_type = indata[cur+4:cur+8]

        # check if chunk already seen
        if not chunk_type in outdata['chunks'].keys():
            outdata['chunks'][chunk_type] = []

        # init chunk
        chunk = {
                'start': cur,
                'end': cur+chunk_len+12,
                'len': chunk_len,
                'errors': []
        }

        # check if chunk has complete data
        chunk['data'] = indata[cur+8:cur+8+chunk_len]
        if len(chunk['data'])<chunk_len:
            chunk['errors'].append('Incomplete chunk: current_len=%d' % len(chunk['data']))
            outdata['errors'].append('Incomplete file')

        else:

            # check if chunk has complete crc
            chunk_crc = indata[cur+8+chunk_len:cur+8+chunk_len+4].encode('hex')
            if len(chunk_crc)<4:
                chunk['errors'].append('Incomplete chunk - current_len=%d' % len(chunk['data']))
                outdata['errors'].append('Incomlete file')

            else:
                chunk['expected_crc'] = int(chunk_crc, 16)
                chunk['actual_crc'] = zlib.crc32(chunk_type + chunk['data']) & 0xffffffff

                if chunk['expected_crc'] != chunk['actual_crc']:
                    chunk['errors'].append('CRC discrepancy')


        # append data in hex, then chunk
        chunk['data'] = chunk['data'].encode('hex')
        outdata['chunks'][chunk_type].append(chunk)
        cur += chunk_len + 12

        # if IEND chunk, then quit
        if chunk_type == 'IEND':
            break


#
# Parse PNG IHDR chunk
def parseihdr(outdata):
    assert('IHDR' in outdata['chunks'].keys())

    if len(outdata['chunks']['IHDR'])!=1:
        outdata['errors'].append('IHDR - abnormal number of chunks: %d' % len(outdata['chunks']['IHDR']))

    data = outdata['chunks']['IHDR'][0]['data'].decode('hex')
    ihdr = {}
    ihdr['width'] = unpack('>I', data[:4])[0]
    ihdr['height'] = unpack('>I', data[4:8])[0]
    ihdr['bit_depth'] = ord(data[8])
    ihdr['color_type'] = ord(data[9])
    ihdr['compression'] = ord(data[10])
    ihdr['filter'] = ord(data[11])
    ihdr['interlace'] = ord(data[12])

    pixel_sample_size = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    ihdr['bits_per_pixel'] = ihdr['bit_depth'] * pixel_sample_size[ihdr['color_type']]

    outdata['headers'] = ihdr


def performchecks(indata, outdata):

    assert('chunks' in outdata.keys())

    # Non-existent chunk
    last_seen = 0
    names = ['IHDR', 'IDAT', 'IEND']
    for name in names:
        if not name in outdata['chunks'].keys():
            outdata['errors'].append('%s - critical chunk does not appear' % name)
            continue

        if outdata['chunks'][name][0]['start'] < last_seen:
            outdata['errors'].append('%s - chunk appears out of order' % name)

        last_seen = outdata['chunks'][name][0]['start']


    # Multiple chunks
    names = ['IHDR', 'PLTE', 'IEND', 'tRNS', 'cHRM', 'gAMA', 'iCCP', 'sBIT', 'sRGB', 'bKGD', 'hIST', 'pHYs', 'tIME']
    for name in names:
        if name in outdata['chunks'].keys():
            chunk_nb = len(outdata['chunks'][name])
            if chunk_nb > 1:
                outdata['errors'].append('%s - Abnormal number of chunk: %d' % (name, chunk_nb))

    # Extra data
    if 'IEND' in outdata['chunks'].keys():
        png_end = outdata['chunks']['IEND'][0]['end']

        if png_end < len(indata):
            outdata['errors'].append('Extra data appears at the end of file, see object[\'extradata\']')
            outdata['extradata'] = indata[png_end:]



def parseidat(outdata, noidatdata):
    if 'IDAT' in outdata['chunks'].keys():
        idat_data = ''
        for chunk in outdata['chunks']['IDAT']:
            idat_data += chunk['data'].decode('hex')

        idat_data = zlib.decompress(idat_data)
        if 'headers' in outdata.keys():
            hdr = outdata['headers']

            if hdr['bits_per_pixel'] % 8 == 0:
                expected_len = hdr['height'] * (1 + hdr['width'] * hdr['bits_per_pixel'] / 8)
                guessed_height = len(idat_data) / (1 + hdr['width'] * hdr['bits_per_pixel'] / 8)

                if hdr['height'] != guessed_height:
                    outdata['errors'].append('IDAT - wrong length, guessed height: %d' % guessed_height)

        if not noidatdata:
            outdata['raw_idat_data'] = idat_data.encode('hex')



# MAIN() !
if __name__=='__main__':
    ap = ArgumentParser()
    ap.add_argument('infile', type=str, nargs='?', default='-', help='Input PNG file [stdin]')
    ap.add_argument('-o', '--output', dest='outfile', type=str, default='-', help='Output file [stdout]')
    ap.add_argument('--ihdr', dest='ihdr', action='store_true', default=False, help='Parse IHDR chunk [false]')
    ap.add_argument('--check', dest='check', action='store_true', default=False, help='Perform random checks [false]')
    ap.add_argument('--idat', dest='idat', action='store_true', default=False, help='Parse IDAT [false]')
    ap.add_argument('--no-idat-data', dest='noidatdata', action='store_true', default=False, help='Don\'t output IDAT data [false]')
    args = ap.parse_args()

    try:
        infile = sys.stdin if args.infile == '-' else open(args.infile, 'rb')

    except IOError, e:
        perror('Unable to open input file %s' % args.infile)

    try:
        outfile = sys.stdout if args.outfile == '-' else open(args.outfile, 'wb')

    except IOError, e:
        perror('Unable to open output file %s' % args.outfile)


    # Read input data
    indata = infile.read()
    infile.close()

    outdata = {'errors':[]}

    if verifysignature(indata):
        parsechunks(indata, outdata)

        if args.ihdr:
            parseihdr(outdata)

        if args.idat:
            parseidat(outdata, args.noidatdata)

        if args.check:
            performchecks(indata, outdata)

    else:
        perror('Invalid file (signature check failed)')

    # Write output data
    outfile.write(json.dumps(outdata))
    outfile.close()
