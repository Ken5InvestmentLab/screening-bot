"""Meaningful causality, missing-session, quantity and policy regression checks."""
import unittest
import numpy as np
import pandas as pd
from common import FEATURES, recipes, production
from prepare import scheduled_outcomes
from search import choose, choose_one, policies, robust, stats
from weak_early_beta.bank_calendar import add_bank_business_days

class SearchContracts(unittest.TestCase):
    def quotes(self):
        days = [pd.Timestamp(add_bank_business_days(pd.Timestamp('2024-02-01').date(), h)) for h in range(25)]
        p = pd.DataFrame({'symbol': '1234', 'date': days, 'actual_open': 100., 'actual_close': 100., 'split_factor': 1., 'source_usable': True})
        return p

    def actions(self, *events):
        return pd.DataFrame(events, columns=['symbol', 'effective_date', 'ratio'])

    def test_calendar_missing_does_not_defer_and_not_affect_shorter_teacher(self):
        p = self.quotes()
        day9 = p.iloc[9].date
        p = p.drop(index=9).reset_index(drop=True)
        r, entry, sessions, which, positions = scheduled_outcomes(p, self.actions())
        self.assertEqual(pd.Timestamp(sessions[which[0], 8]), day9)
        self.assertEqual(positions[0, 8], -1)
        self.assertTrue(np.isnan(r[0, 16:18]).all())
        self.assertEqual(r[0, 9], 0)  # 5-session teacher remains valid.

    def test_split_after_entry_preserves_original_cost(self):
        p = self.quotes(); action_day = p.iloc[3].date
        p.loc[p.date.lt(action_day), 'split_factor'] = 2
        p.loc[p.date.ge(action_day), ['actual_open', 'actual_close']] = 50
        r, entry, *_ = scheduled_outcomes(p, self.actions(('1234', action_day, 2)))
        self.assertEqual(entry[0], 100)
        self.assertAlmostEqual(r[0, 9], 0)

    def test_entry_date_action_already_in_price(self):
        p = self.quotes(); action_day = p.iloc[1].date
        p.loc[p.date.lt(action_day), 'split_factor'] = 2
        p.loc[p.date.ge(action_day), ['actual_open', 'actual_close']] = 50
        r, entry, *_ = scheduled_outcomes(p, self.actions(('1234', action_day, 2)))
        self.assertEqual(entry[0], 50)
        self.assertAlmostEqual(r[0, 9], 0)

    def test_fraction_cannot_be_restored_by_later_split(self):
        p = self.quotes(); a, b = p.iloc[3].date, p.iloc[6].date
        p.loc[p.date.ge(a) & p.date.lt(b), 'split_factor'] = 3
        p.loc[p.date.ge(a) & p.date.lt(b), ['actual_open', 'actual_close']] = 300
        r, *_ = scheduled_outcomes(p, self.actions(('1234', a, 1/3), ('1234', b, 3)))
        self.assertEqual(r[0, 1], 0)
        self.assertTrue(np.isnan(r[0, 9]))
        self.assertTrue(np.isnan(r[0, 19]))

    def test_quarantined_endpoint_not_evaluated(self):
        p = self.quotes(); p.loc[5, 'source_usable'] = False
        r, *_ = scheduled_outcomes(p, self.actions())
        self.assertTrue(np.isnan(r[0, 9]))
        self.assertEqual(r[0, 7], 0)

    def test_winning_tie_is_not_resolved_using_symbol_or_future_return(self):
        z = pd.DataFrame({'row_id': [1, 2], 'symbol': ['1111', '2222'], 'cdf': [.99, .99], 'score': [.8, .8], 'volr20': [1, 1], 'body_pct': [0, 0], 'future_return': [1, -1]})
        self.assertIsNone(choose_one(z, 'score'))
        self.assertIsNone(choose_one(z, 'fusion'))

    def test_policy_uses_signal_data_and_cooldown(self):
        z = pd.DataFrame({'row_id': [1, 2, 3], 'symbol': ['1111']*3, 'date': pd.to_datetime(['2024-02-01', '2024-02-02', '2024-02-09']),
                          'cdf': [.999]*3, 'score': [.8]*3, 'volr20': [1]*3, 'body_pct': [0]*3,
                          'med_ret5': [-.01]*3, 'ret10': [0]*3, 'med_ret1': [0]*3,
                          'actual_volume': [10000]*3, 'previous_actual_volume': [20000]*3})
        ordinal = dict(zip(z.date.to_numpy(), [0, 1, 6]))
        policy = dict(gate=.99, rank='score', market=0, retmax=None, medmin=None, vol=1, cooldown=5)
        self.assertEqual(choose(z, policy, ordinal).tolist(), [1, 3])

    def test_grid_and_no_tiny_sample_acceptance(self):
        self.assertEqual(len(recipes()), 864)
        self.assertEqual(len(list(policies())), 18)
        self.assertEqual(len(list(policies(True))), 2400)
        m = stats(np.full(5, .1)); m.update(n2023=2, n2024=3)
        self.assertFalse(robust(m))
        m = stats(np.full(40, .02)); m.update(n2023=20, n2024=20)
        self.assertTrue(robust(m))

    def test_training_cutoff_is_strictly_before_month(self):
        end = np.array(['2024-02-29', '2024-03-01', '2024-03-04'], dtype='datetime64[D]')
        self.assertEqual((end < pd.Period('2024-03').start_time.to_datetime64()).tolist(), [True, False, False])

if __name__ == '__main__': unittest.main()
