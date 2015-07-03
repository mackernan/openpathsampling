import matplotlib
import matplotlib.pyplot as plt

import openpathsampling as paths

class LiveVisualization(object):
    def __init__(self, cv_x, cv_y, range_x, range_y, output_directory=None):
        self.cv_x = cv_x
        self.cv_y = cv_y
        self.range_x = range_x
        self.range_y = range_y
        self.output_directory = output_directory
        self.extent = [range_x[0], range_x[1], range_y[0], range_y[1]]
        self.xlim = [range_x[0], range_x[1]]
        self.ylim = [range_y[0], range_y[1]]
        self.background = None


    def draw(self, mcstep):
        if self.background is not None:
            self.fig = (self.background)
            ax = self.fig.axes[0]
        else:
            self.fig, ax = plt.subplots()
        ax.set_xlim(self.xlim)
        ax.set_ylim(self.ylim)
        # draw the background
        # draw the active trajectories
        for sample in mcstep.active:
            ax.plot(self.cv_x(sample.trajectory), 
                    self.cv_y(sample.trajectory), linewidth=2, zorder=2);
            # draw arrowheads at the end of each active

        # draw the trials
            # draw arrowheads at the end of each trial
        # decorate by trial type

        return self.fig


    def draw_ipynb(self, mcstep):
        try:
            import IPython.display
        except ImportError:
            pass
        else:
            IPython.display.clear_output(wait=True)
            fig = self.draw(mcstep)
            IPython.display.display(fig);
            plt.close() # prevents crap in the output

    def draw_png(self, mcstep):
        pass
