#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
#
#       fits2galstarinput.py
#       
#       Copyright 2012 Greg <greg@greg-G53JW>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#       
#       


import os, sys, argparse
from os.path import abspath

import healpy as hp
import numpy as np
import pyfits

import matplotlib.pyplot as plt



def main():
	parser = argparse.ArgumentParser(prog='fits2galstarinput.py', description='Generate galstar input files from LSD fits output.', add_help=True)
	parser.add_argument('FITS', type=str, help='FITS output from LSD.')
	parser.add_argument('out', type=str, help='Output filename.')
	parser.add_argument('-n', '--nside', type=int, default=512, help='healpix nside parameter (default: 512).')
	parser.add_argument('-r', '--ring', action='store_true', help='Use healpix ring ordering. If not specified, nested ordering is used.')
	parser.add_argument('-b', '--bounds', type=float, nargs=4, default=None, help='Restrict pixels to region enclosed by: l_min, l_max, b_min, b_max')
	parser.add_argument('-sp', '--split', type=int, default=1, help='Split into an arbitrary number of tarballs.')
	parser.add_argument('-min', '--min_stars', type=int, default=15, help='Minimum # of stars in pixel.')
	parser.add_argument('-vis', '--visualize', action='store_true', help='Show plot of footprint')
	if 'python' in sys.argv[0]:
		offset = 2
	else:
		offset = 1
	values = parser.parse_args(sys.argv[offset:])
	
	# Load the stars from the FITS file
	d,h = pyfits.getdata(abspath(values.FITS), header=True)
	print 'Loaded %d stars.' % d.shape[0]
	
	# Convert (l, b) to spherical coordinates (physics convention)
	theta = np.pi/180. * (90. - d['b'])
	phi = np.pi/180. * d['l']
	l_min = np.min(d['l'])
	l_max = np.max(d['l'])
	b_min = np.min(d['b'])
	b_max = np.max(d['b'])
	print ''
	print 'Bounds on stars present:'
	print '\t(l_min, l_max) = (%.3f, %.3f)' % (l_min, l_max)
	print '\t(b_min, b_max) = (%.3f, %.3f)' % (b_min, b_max)
	print ''
	
	# Convert spherical coordinates to healpix
	N_arr = hp.ang2pix(values.nside, theta, phi, nest=(not values.ring))
	
	# Get unique pixel numbers
	N_unique = np.unique(N_arr)
	print '%d unique healpix pixel(s) present.' % N_unique.size
	
	# Open the output files (which will be galstar .in files)
	fout = None
	if values.split < 1:
		print '--split must be positive.'
		return 1
	if values.split > 1:
		base = abspath(values.out)
		if base.endswith('.in'):
			base = base[:-3]
		fout = [open('%s_%d.in' % (base, i), 'wb') for i in range(values.split)]
	else:
		fout = [open(values.out, 'w')]
	
	# Keep track of number of stars saved
	N_pix_used = np.zeros(values.split, dtype=np.uint32)
	N_saved = np.zeros(values.split, dtype=np.uint64)
	N_stars_min = 1.e100
	N_stars_max = -1.
	
	# Sort the stars by pixel
	indices = N_arr.argsort()
	N_arr = N_arr[indices]
	pix_map = None
	if values.visualize:
		pix_map = np.zeros(12 * values.nside**2, dtype=np.float64)
	
	# Leave space in each file to record the number of files
	N_pix_used_str = N_pix_used.tostring()
	for i,f in enumerate(fout):
		f.write(N_pix_used_str[4*i:4*i+4])
	
	# Break data into healpix pixels
	newblock = np.where(np.diff(N_arr))[0] + 1
	start = 0
	l_min, l_max, b_min, b_max = 1.e100, -1.e100, 1.e100, -1.e100
	for end in np.concatenate((newblock,[-1])):
		N = N_arr[start]
		
		# Filter pixels by bounds
		if values.bounds != None:
			theta_0, phi_0 = hp.pix2ang(values.nside, N, nest=(not values.ring))
			l_0 = 180./np.pi * phi_0
			b_0 = 90. - 180./np.pi * theta_0
			if (l_0 < values.bounds[0]) or (l_0 > values.bounds[1]) or (b_0 < values.bounds[2]) or (b_0 > values.bounds[3]):
				start = end
				continue
			else:
				if l_0 < l_min:
					l_min = l_0
				if l_0 > l_max:
					l_max = l_0
				if b_0 < b_min:
					b_min = b_0
				if b_0 > b_max:
					b_max = b_0
		
		sel = indices[start:end]
		
		#diff_tmp = N_arr[start+1:end] - N_arr[start:end-1]
		#if np.sum(diff_tmp) != 0:
		#	print diff_tmp
		
		# Get stars in this pixel
		grizy = d['mean'][sel]
		err = d['err'][sel]
		
		# Fix errors for stars with NaN or zero magnitude or error in any band
		mask_zero_mag = (grizy == 0.)
		mask_zero_err = (err == 0.)
		mask_nan_mag = np.isnan(grizy)
		mask_nan_err = np.isnan(err)
		
		grizy[mask_nan_mag] = 0.
		err[mask_zero_err] = 1.e10
		err[mask_nan_err] = 1.e10
		err[mask_zero_mag] = 1.e10
		
		mask_detect = np.sum(grizy, axis=1).astype(np.bool)
		mask_informative = (np.sum(err > 1.e10, axis=1) < 3).astype(np.bool)
		mask_keep = np.logical_and(mask_detect, mask_informative)
		
		# Create the output matrix
		outarr = np.hstack((grizy[mask_keep], err[mask_keep])).astype(np.float64)
		
		# Write Header
		N_stars = np.array([outarr.shape[0]], np.uint32)
		if N_stars < values.min_stars:
			start = end
			continue
		findex = np.argmin(N_saved)
		pix_index = np.array([N], dtype=np.uint32)
		gal_lb = np.array([np.mean(d['l'][sel]), np.mean(d['b'][sel])], dtype=np.float64)
		fout[findex].write(pix_index.tostring())	# Pixel index	(uint32)
		fout[findex].write(gal_lb.tostring())		# (l, b)		(2 x float64)
		fout[findex].write(N_stars.tostring())		# N_stars		(uint32)
		
		# Write magnitudes and errors
		fout[findex].write(outarr.tostring())		# 5xmag, 5xerr	(10 x float64)
		
		# Record number of stars saved to pixel
		N_pix_used[findex] += 1
		N_saved[findex] += outarr.shape[0]
		if outarr.shape[0] < N_stars_min:
			N_stars_min = outarr.shape[0]
		if outarr.shape[0] > N_stars_max:
			N_stars_max = outarr.shape[0]
		if values.visualize:
			pix_map[N] = outarr.shape[0]
		
		start = end
	
	# Return to beginning of each file and write number of pixels in file
	N_pix_used_str = N_pix_used.tostring()
	for i,f in enumerate(fout):
		f.seek(0)
		f.write(N_pix_used_str[4*i:4*i+4])
		f.close()
	
	if np.sum(N_pix_used) != 0:
		print 'Saved %d stars from %d healpix pixels to %d galstar input file(s) (per pixel min: %d, max: %d, mean: %.1f).' % (np.sum(N_saved), np.sum(N_pix_used), values.split, N_stars_min, N_stars_max, float(np.sum(N_saved))/float(np.sum(N_pix_used)))
	else:
		print 'No pixels in specified bounds.'
	
	if (values.bounds != None) and (np.sum(N_pix_used) != 0):
		print ''
		print 'Bounds of included pixel centers:'
		print '\t(l_min, l_max) = (%.3f, %.3f)' % (l_min, l_max)
		print '\t(b_min, b_max) = (%.3f, %.3f)' % (b_min, b_max)
	
	# Show footprint of stored pixels on sky
	if values.visualize:
		hp.visufunc.mollview(map=np.log(pix_map), nest=(not values.ring), title='Footprint', coord='G', xsize=5000)
		plt.show()
	
	return 0

if __name__ == '__main__':
	main()

