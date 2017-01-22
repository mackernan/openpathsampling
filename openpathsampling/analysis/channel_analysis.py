import collections
import pandas as pd
import numpy as np

from openpathsampling.netcdfplus import StorableNamedObject


class ChannelAnalysis(StorableNamedObject):
    """Analyze path sampling simulation for multiple channels.

    User defines several channels (e.g., mechanisms) as :class:`.Ensemble`
    objects. This checks which channels each path satisfies, and provides
    analysis of switching and residence.

    Parameters
    ----------
    steps : iterable of :class:`.MCStep`
        the steps to analyze
    channels: dict of {string: :class:`.Ensemble`}
        names (keys) and ensembles (values) representing subtrajectories of the
        channels of interest
    replica: int
        replica ID to analyze from the steps, default is 0.
    """
    def __init__(self, steps, channels, replica=0):
        super(ChannelAnalysis, self).__init__()
        self.channels = channels
        if steps is None:
            steps = []
        self.replica = replica

        self._treat_multiples = 'all'
        self._results = {c: [] for c in self.channels.keys() + [None]}
        if len(steps) > 0:
            self._analyze(steps)

    # separate this because I think much of the code might be generalized
    # later where step_num could be something else
    @staticmethod
    def _step_num(step):
        """Return ordinal number for the given input object.

        Abstracted so that other things might replace it.

        Parameters
        ----------
        step : :class:`.MCStep`
            the step

        Returns
        -------
        int :
            MC cycle number
        """
        return step.mccycle

    def _analyze(self, steps):
        """Primary analysis routine.

        Converts the input steps to an internal ._results dictionary of
        channel name to list of (start, end) tuples for when that channel is
        occupied.

        Parameters
        ----------
        steps : iterable of :class:`.MCStep`
            the steps to analyze
        """
        # for now, this assumes only one ensemble per channel
        # (would like that to change in the future)
        prev_traj = None
        last_start = {c: None for c in self._results}
        for step in steps:
            step_num = self._step_num(step)
            traj = step.active[self.replica].trajectory
            if prev_traj is None:
                prev_result = {c: len(self.channels[c].split(traj)) > 0
                               for c in self.channels}
                prev_result[None] = not any(prev_result.values())
                for c in last_start:
                    if prev_result[c] is True:
                        last_start[c] = step_num
            # re-use previous if the trajectory hasn't changed
            if traj is prev_traj:
                result = prev_result
            else:
                result = {c: len(self.channels[c].split(traj)) > 0
                          for c in self.channels}
                result[None] = not any(result.values())
                changed = [c for c in result if result[c] != prev_result[c]]
                for c in changed:
                    if result[c] is True:
                        # switched from False to True: entered this label
                        last_start[c] = step_num
                    else:
                        # switched from True to False: exited this label
                        finish = step_num
                        self._results[c] += [(last_start[c], finish)]
                        last_start[c] = None
            prev_traj = traj
            prev_result = result
        # finish off any extras
        next_step = step_num + 1 # again, this can be changed
        for c in self._results:
            if last_start[c] is not None:
                if len(self._results[c]) > 0:
                    # don't do double it if it's already there
                    if self._results[c][-1][1] != step_num:
                        self._results[c] += [(last_start[c], next_step)]
                    # note: is the else: of the above even possible?
                    # namely, do we need the if statement? should test that
                else:
                    self._results[c] += [(last_start[c], next_step)]

    @property
    def treat_multiples(self):
        return self._treat_multiples

    @treat_multiples.setter
    def treat_multiples(self, value):
        value = value.lower()
        if value not in ['all', 'newest', 'oldest', 'multiple']:
            raise ValueError("Invalid value for treat_multiples: " +
                             str(value))
        self._treat_multiples = value

    @staticmethod
    def _expand_results(results):
        expanded = [(domain[0], domain[1], frozenset([channel]))
                    for channel in results for domain in results[channel]]
        return sorted(expanded, key=lambda tup: tup[0])

    @staticmethod
    def _labels_by_step_newest(expanded_results):
        relabeled = []
        previous = expanded_results[0]
        for current in expanded_results[1:]:
            relabeled += [(previous[0], current[0], previous[2])]
            previous = current
        relabeled += [expanded_results[-1]]
        return relabeled

    @staticmethod
    def _labels_by_step_oldest(expanded_results):
        relabeled = []
        previous = expanded_results[0]
        for current in expanded_results[1:]:
            if current[1] > previous[1]:
                # ends after last one ended
                # if this isn't true, this one gets skipped
                # if it is true, then previous is used
                relabeled += [previous]
                # save the new starting point
                previous = (previous[1], current[1], current[2])
            else:
                pass # for testing
        if relabeled[-1] != previous:
            relabeled += [previous]
        else:
            pass # for testing
        return relabeled

    @staticmethod
    def _labels_by_step_multiple(expanded_results):
        relabeled = []
        # start events are times when a channel is added to the active
        # finish events are when channel is removed from the active
        # both are dicts of time to a set of channels
        start_events = collections.defaultdict(set)
        finish_events = collections.defaultdict(set)
        for event in expanded_results:
            start_events[event[0]] |= set(event[2])
            finish_events[event[1]] |= set(event[2])

        all_event_steps = set(start_events.keys()) | set(finish_events.keys())
        active_channels = set([])
        prev_step_num = None
        # note to self: this is some elegant freaking code
        for step_num in sorted(list(all_event_steps)):
            if prev_step_num is not None:
                relabeled += [(prev_step_num, step_num,
                               frozenset(active_channels))]

            # defaultdict gives empty if doesn't exist
            active_channels -= finish_events[step_num]
            active_channels |= start_events[step_num]

            prev_step_num = step_num

        return relabeled

    def labels_by_step(self, treat_multiples=None):
        if treat_multiples is None:
            treat_multiples = self.treat_multiples
        expanded_results = self._expand_results(self._results)
        method = {
            'all': lambda x: x,
            'newest': self._labels_by_step_newest,
            'oldest': self._labels_by_step_oldest,
            'multiple': self._labels_by_step_multiple
        }[treat_multiples]
        return method(expanded_results)

    @staticmethod
    def _labels_as_sets_sort_function(label):
        ll = sorted(list(label))
        return [len(ll)] + ll

    @staticmethod
    def label_to_string(label):
        return ",".join(sorted([str(l) for l in list(label)]))

    @property
    def switching_matrix(self):
        labeled_results = self.labels_by_step()
        labels_in_order = [ll[2] for ll in labeled_results]
        labels_set = set(labels_in_order)
        sorted_set_labels = sorted(list(labels_set),
                                   key=self._labels_as_sets_sort_function)
        sorted_labels = [self.label_to_string(e) for e in sorted_set_labels]
        switches = [(self.label_to_string(labels_in_order[i]),
                     self.label_to_string(labels_in_order[i+1]))
                    for i in range(len(labeled_results)-1)]
        switch_count = collections.Counter(switches)
        df = pd.DataFrame(index=sorted_labels, columns=sorted_labels)
        for switch in switch_count:
            df.set_value(index=switch[0], col=switch[1],
                         value=switch_count[switch])

        df = df.fillna(0)
        return df

    @property
    def residence_times(self):
        labeled_results = self.labels_by_step()
        durations = [(self.label_to_string(step[2]), step[1] - step[0])
                     for step in labeled_results]
        results = collections.defaultdict(list)
        for dur in durations:
            results[dur[0]] += [dur[1]]
        return results

    @property
    def total_time(self):
        residences = self.residence_times
        results = collections.defaultdict(int)
        for channel in residences:
            results[channel] = sum(residences[channel])
        return results

    def status(self, step_number):
        """Which channels were active at a given step number"""
        treat_multiples = self.treat_multiples
        if self.treat_multiples == 'all':
            treat_multiples = 'multiple'
        labeled_results = self.labels_by_step(treat_multiples)
        for step in labeled_results:
            if step[0] <= step_number < step[1]:
                return self.label_to_string(step[2])
        raise RuntimeError("Step " + str(step_number) + " outside of range."
                           + " Max step: " + str(labeled_results[-1][1]))
