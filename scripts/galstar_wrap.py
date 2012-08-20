import numpy, tempfile, os, galstar_io

def write_infile(filename, mag, err, l=0., b=90.):
    if isinstance(filename, str):
        f = open(filename, 'wb')
    f.write(numpy.array([1], dtype='u4').tostring()) # one pixel
    f.write(numpy.array([0], dtype='u4').tostring()) # healpix pix num
    f.write(numpy.array([l, b], dtype='f8').tostring())
    if len(mag.shape) > 1:
        nstars = mag.shape[0]
    else:
        nstars = 1
    f.write(numpy.array([nstars], dtype='u4').tostring())
    dtype = [('obj_id', 'u8'), ('l_star', 'f8'), ('b_star', 'f8'), ('mag', '5f8'), ('err', '5f8')]
    dat = numpy.zeros(nstars, dtype=dtype)
    dat['mag'] = mag
    dat['err'] = err
    f.write(dat.tostring())

def probsurf_galstar(mag, err, l=0., b=90.):
    infile = tempfile.NamedTemporaryFile()
    write_infile(infile.name, mag, err, l, b)
    outsurffile = tempfile.NamedTemporaryFile()
    outstatsfile = tempfile.NamedTemporaryFile()
    logfile = tempfile.NamedTemporaryFile()
    os.system('/n/home13/schlafly/galstar/optimized/galstar %s:DM[5,20,120],Ar[0,15,750] --statsfile %s --infile %s 0 --giant &>%s' %
              (outsurffile.name, outstatsfile.name, infile.name, logfile.name))
    bounds, surfs = galstar_io.load_bins(outsurffile.name)
    converged, lnZ, mean, cov = galstar_io.load_stats(outstatsfile.name)
    log = logfile.read()
    return bounds, surfs, converged, lnZ, mean, cov, log
    
    
