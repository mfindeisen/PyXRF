# ######################################################################
# Copyright (c) 2014, Brookhaven Science Associates, Brookhaven        #
# National Laboratory. All rights reserved.                            #
#                                                                      #
# Redistribution and use in source and binary forms, with or without   #
# modification, are permitted provided that the following conditions   #
# are met:                                                             #
#                                                                      #
# * Redistributions of source code must retain the above copyright     #
#   notice, this list of conditions and the following disclaimer.      #
#                                                                      #
# * Redistributions in binary form must reproduce the above copyright  #
#   notice this list of conditions and the following disclaimer in     #
#   the documentation and/or other materials provided with the         #
#   distribution.                                                      #
#                                                                      #
# * Neither the name of the Brookhaven Science Associates, Brookhaven  #
#   National Laboratory nor the names of its contributors may be used  #
#   to endorse or promote products derived from this software without  #
#   specific prior written permission.                                 #
#                                                                      #
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS  #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT    #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS    #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE       #
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,           #
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES   #
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR   #
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)   #
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,  #
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OTHERWISE) ARISING   #
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE   #
# POSSIBILITY OF SUCH DAMAGE.                                          #
########################################################################
from __future__ import absolute_import
__author__ = 'Li Li'

import six
import numpy as np
from collections import OrderedDict
from scipy.interpolate import interp1d, interp2d
import copy

import matplotlib
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import matplotlib.cm as cm

from mpl_toolkits.axes_grid1 import ImageGrid
from atom.api import Atom, Str, observe, Typed, Int, List, Dict, Bool, Float

import logging
logger = logging.getLogger()


class DrawImageAdvanced(Atom):
    """
    This class performs 2D image rendering, such as showing multiple
    2D fitting or roi images based on user's selection.

    Attributes
    ----------
    img_data : dict
        dict of 2D array
    fig : object
        matplotlib Figure
    file_name : str
    stat_dict : dict
        determine which image to show
    data_dict : dict
        multiple data sets to plot, such as fit data, or roi data
    data_dict_keys : list
    data_opt : int
        index to show which data is chosen to plot
    dict_to_plot : dict
        selected data dict to plot, i.e., fitting data or roi is selected
    items_in_selected_group : list
        keys of dict_to_plot
    scale_opt : str
        linear or log plot
    color_opt : str
        orange or gray plot
    scaler_norm_dict : dict
        scaler normalization data, from data_dict
    scaler_items : list
        keys of scaler_norm_dict
    scaler_name_index : int
        index to select on GUI level
    scaler_data : None or numpy
        selected scaler data
    plot_all : Bool
        to control plot all of the data or not
    x_pos : list
        define data range in horizontal direction
    y_pos : list
        define data range in vertical direction
    pixel_or_pos : int
        index to choose plot with pixel or with positions
    pixel_or_pos_for_plot : None, array
        argument passed to extent in imshow of matplotlib
    interpolation_opt: bool
        choose to interpolate 2D image in terms of x,y or not
    limit_dict : Dict
        save low and high limit for image scaling
    """

    fig = Typed(Figure)
    stat_dict = Dict()
    data_dict = Dict()
    data_dict_keys = List()
    data_opt = Int(0)
    dict_to_plot = Dict()
    items_in_selected_group = List()

    scale_opt = Str('Linear')
    color_opt = Str('jet')
    img_title = Str()

    scaler_norm_dict = Dict()
    scaler_items = List()
    scaler_name_index = Int()
    scaler_data = Typed(object)

    plot_all = Bool(False)
    x_pos = List()
    y_pos = List()

    pixel_or_pos = Int(0)
    pixel_or_pos_for_plot = Typed(object)
    interpolation_opt = Bool(True)
    data_dict_default = Dict()
    limit_dict = Dict()
    scatter_show = Bool(False)

    def __init__(self):
        self.fig = plt.figure(figsize=(4,4))
        self.pixel_or_pos_for_plot = None
        matplotlib.rcParams['axes.formatter.useoffset'] = True

    def data_dict_update(self, change):
        """
        Observer function to be connected to the fileio model
        in the top-level gui.py startup

        Parameters
        ----------
        changed : dict
            This is the dictionary that gets passed to a function
            with the @observe decorator
        """
        self.data_dict = change['value']

    def set_default_dict(self, data_dict):
        self.data_dict_default = copy.deepcopy(data_dict)

    @observe('data_dict')
    def init_plot_status(self, change):
        # initiate the plotting status once new data is coming
        self.data_opt = 0
        # init of scaler for normalization
        self.scaler_name_index = 0
        self.data_dict_keys = []
        self.data_dict_keys = list(self.data_dict.keys())
        logger.debug('The following groups are included for 2D image display: {}'.format(self.data_dict_keys))

        scaler_groups = [v for v in list(self.data_dict.keys()) if 'scaler' in v]
        if len(scaler_groups) > 0:
            #self.scaler_group_name = scaler_groups[0]
            self.scaler_norm_dict = self.data_dict[scaler_groups[0]]
            # for GUI purpose only
            self.scaler_items = []
            self.scaler_items = list(self.scaler_norm_dict.keys())
            self.scaler_data = None

        # init of pos values
        self.pixel_or_pos = 0

        if 'positions' in self.data_dict:
            try:
                logger.info('get pos {}'.format(list(self.data_dict['positions'].keys())))
                self.x_pos = list(self.data_dict['positions']['x_pos'][0, :])
                self.y_pos = list(self.data_dict['positions']['y_pos'][:, -1])
                # when we use imshow, the x and y start at lower left,
                # so flip y, we want y starts from top left
                self.y_pos.reverse()

            except KeyError:
                pass

        else:
            self.x_pos = []
            self.y_pos = []

        self.show_image()

    @observe('data_opt')
    def _update_file(self, change):
        try:
            if self.data_opt == 0:
                self.dict_to_plot = {}
                self.items_in_selected_group = list(self.dict_to_plot.keys())
                self.set_stat_for_all(bool_val=False)
                self.img_title = ''
            elif self.data_opt > 0:
                self.set_stat_for_all(bool_val=False)
                plot_item = sorted(self.data_dict_keys)[self.data_opt-1]
                self.img_title = str(plot_item)
                self.dict_to_plot = self.data_dict[plot_item]

                # for GUI purpose only
                self.items_in_selected_group = []
                self.items_in_selected_group = list(self.dict_to_plot.keys())
                self.set_stat_for_all(bool_val=False)
        except IndexError:
            pass

    # @observe('plot_item')
    # def _update_file(self, change):
    #     self.set_stat_for_all(bool_val=False)
    #     self.items_in_selected_group = []
    #     self.dict_to_plot = self.data_dict[self.plot_item]
    #     self.items_in_selected_group = self.dict_to_plot.keys()
    #     self.set_stat_for_all(bool_val=False)

    @observe('scaler_name_index')
    def _get_scaler_data(self, change):
        if self.scaler_name_index == 0:
            self.scaler_data = None
        else:
            scaler_name = self.scaler_items[self.scaler_name_index-1]
            #self.scaler_data = self.data_dict[self.scaler_group_name][scaler_name]
            self.scaler_data = self.scaler_norm_dict[scaler_name]
            logger.info('Use scaler data to normalize, '
                        'and the shape of scaler data is {}'.format(self.scaler_data.shape))
        self.show_image()

    @observe('scale_opt', 'color_opt')
    def _update_scale(self, change):
        if change['type'] != 'create':
            self.show_image()

    @observe('pixel_or_pos')
    def _update_pp(self, change):
        if change['type'] != 'create':
            if change['value'] == 0:
                self.pixel_or_pos_for_plot = None
            elif change['value'] > 0 and len(self.x_pos) > 0 and len(self.y_pos) > 0:
                self.pixel_or_pos_for_plot = (self.x_pos[0], self.x_pos[-1],
                                              self.y_pos[0], self.y_pos[-1])
            self.show_image()

    @observe('plot_all')
    def _update_all_plot(self, change):
        if self.plot_all is True:
            self.set_stat_for_all(bool_val=True)
        else:
            self.set_stat_for_all(bool_val=False)

    @observe('scatter_show')
    def _change_image_plot_method(self, change):
        if change['type'] != 'create':
            self.show_image()

    # @observe('interpolation_opt')
    # def _interp_update(self, change):
    #     """Do interpolation in terms of position or not.
    #     """
    #     if change['type']=='create':
    #         return
    #     #try:
    #     self.data_dict = copy.deepcopy(self.data_dict_default)
    #     print(self.data_dict.keys())
    #     uninterp_list = ['positions']
    #     rangex = self.data_dict['positions']['x_pos'][0, :]
    #     rangey = self.data_dict['positions']['x_pos'][:, 0]
    #     start_x = rangex[0]
    #     start_y = rangey[0]
    #
    #     dimv = self.data_dict['positions']['x_pos'].shape
    #     #if beamline_name in ['HXN']:
    #     #result_tmp = {}
    #     if self.interpolation_opt is True:
    #         logger.info('Interpolating image... ')
    #         all_dict_tmp = {}
    #         for k1, v1 in six.iteritems(self.data_dict):
    #             if 'position' == k1:
    #                 continue
    #             #if 'fit' in k1 or 'scaler' in k1:
    #             result_tmp = {}
    #             shapev = [dimv[1], dimv[0]]  # horizontal first, then vertical, different from dim in numpy
    #             for k, v in six.iteritems(v1):
    #                 interp_d = interp1d_scan(shapev, rangex, rangey, start_x, start_y,
    #                                          self.data_dict['positions']['x_pos'],
    #                                          self.data_dict['positions']['y_pos'],
    #                                          v)
    #                 interp_d[np.isnan(interp_d)] = 0
    #                 result_tmp[k] = interp_d
    #             all_dict_tmp.update(result_tmp)
    #         self.data_dict.update(all_dict_tmp)
    #
    #     self.show_image()

    def set_stat_for_all(self, bool_val=False):
        """
        Set plotting status for all the 2D images.
        """
        self.stat_dict.clear()
        self.stat_dict = {k: bool_val for k in self.items_in_selected_group}

        self.limit_dict.clear()
        self.limit_dict = {k: {'low':0.0, 'high': 100.0} for k in self.items_in_selected_group}

    def show_image(self):
        self.fig.clf()
        stat_temp = self.get_activated_num()
        stat_temp = OrderedDict(sorted(six.iteritems(stat_temp), key=lambda x: x[0]))

        low_lim = 1e-4  # define the low limit for log image
        plot_interp = 'Nearest'
        name_not_scalable = ['r_squared']  # do not apply scaler norm on those data

        if self.scaler_data is not None:
            if len(self.scaler_data[self.scaler_data == 0]) > 0:
                logger.warning('scaler data has zero values at {}'.format(np.where(self.scaler_data == 0)))
                self.scaler_data[self.scaler_data == 0] = np.mean(self.scaler_data[self.scaler_data > 0])
                logger.warning('Use mean value {} instead for those points'.format(np.mean(self.scaler_data[self.scaler_data > 0])))

        grey_use = self.color_opt

        ncol = int(np.ceil(np.sqrt(len(stat_temp))))
        try:
            nrow = int(np.ceil(len(stat_temp)/float(ncol)))
        except ZeroDivisionError:
            ncol = 1
            nrow = 1

        a_pad_v = 0.8
        a_pad_h = 0.3

        grid = ImageGrid(self.fig, 111,
                         nrows_ncols=(nrow, ncol),
                         axes_pad=(a_pad_v, a_pad_h),
                         cbar_location='right',
                         cbar_mode='each',
                         cbar_size='7%',
                         cbar_pad='2%',
                         share_all=True)

        if self.scale_opt == 'Linear':
            for i, (k, v) in enumerate(six.iteritems(stat_temp)):

                if self.scaler_data is not None:
                    if k in name_not_scalable:
                        data_dict = self.dict_to_plot[k]
                    else:
                        data_dict = self.dict_to_plot[k]/self.scaler_data
                else:
                    data_dict = self.dict_to_plot[k]

                lowv = self.limit_dict[k]['low']/100.0
                highv = self.limit_dict[k]['high']/100.0
                low_limit = (np.max(data_dict)-np.min(data_dict))*lowv + np.min(data_dict)
                high_limit = (np.max(data_dict)-np.min(data_dict))*highv + np.min(data_dict)

                if self.scatter_show is not True:
                    im = grid[i].imshow(data_dict,
                                        cmap=grey_use,
                                        interpolation=plot_interp,
                                        extent=self.pixel_or_pos_for_plot,
                                        origin='upper',
                                        clim=(low_limit, high_limit))
                else:
                    im = grid[i].scatter(self.data_dict['positions']['x_pos'],
                                         self.data_dict['positions']['y_pos'],
                                         c=data_dict,marker='s', s=500, alpha=0.8,
                                         cmap=grey_use,
                                         linewidths=1, linewidth=0,
                                         clim=(low_limit, high_limit))
                    # for scatter plot, the origin is at lower, no way to change that, so flip y
                    grid[i].set_xlim(self.x_pos[0], self.x_pos[-1])
                    grid[i].set_ylim(max([self.y_pos[0], self.y_pos[-1]]), min([self.y_pos[0], self.y_pos[-1]]))

                grid_title = k #self.file_name+'_'+str(k)
                if self.pixel_or_pos_for_plot is not None:
                    title_x = self.pixel_or_pos_for_plot[0]
                    title_y = self.pixel_or_pos_for_plot[3] + (self.pixel_or_pos_for_plot[3] -
                                                               self.pixel_or_pos_for_plot[2])*0.04
                else:
                    title_x = 0
                    title_y = - data_dict.shape[0]*0.05
                grid[i].text(title_x, title_y, grid_title)

                grid.cbar_axes[i].colorbar(im)
                grid[i].get_xaxis().get_major_formatter().set_useOffset(False)
                grid[i].get_yaxis().get_major_formatter().set_useOffset(False)
        else:
            for i, (k, v) in enumerate(six.iteritems(stat_temp)):

                if self.scaler_data is not None:
                    if k in name_not_scalable:
                        data_dict = self.dict_to_plot[k]
                    else:
                        data_dict = self.dict_to_plot[k]/self.scaler_data

                else:
                    data_dict = self.dict_to_plot[k]

                maxz = np.max(data_dict)

                im = grid[i].imshow(data_dict,
                                    norm=LogNorm(vmin=low_lim*maxz,
                                                 vmax=maxz),
                                    cmap=grey_use,
                                    interpolation=plot_interp,
                                    extent=self.pixel_or_pos_for_plot)
                grid[i].get_xaxis().get_major_formatter().set_useOffset(False)
                grid[i].get_yaxis().get_major_formatter().set_useOffset(False)
                grid_title = k #self.file_name+'_'+str(k)
                if self.pixel_or_pos_for_plot is not None:
                    title_x = self.pixel_or_pos_for_plot[0]
                    title_y = self.pixel_or_pos_for_plot[3] + (self.pixel_or_pos_for_plot[3] -
                                                               self.pixel_or_pos_for_plot[2])*0.05

                else:
                    title_x = 0
                    title_y = - data_dict.shape[0]*0.05
                grid[i].text(title_x, title_y, grid_title)
                grid.cbar_axes[i].colorbar(im)

        #self.fig.tight_layout(pad=4.0, w_pad=0.8, h_pad=0.8)
        #self.fig.tight_layout()
        self.fig.suptitle(self.img_title, fontsize=20)
        self.fig.canvas.draw_idle()

    def get_activated_num(self):
        return {k: v for (k, v) in six.iteritems(self.stat_dict) if v is True}
