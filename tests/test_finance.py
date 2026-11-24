import unittest
from main import projection
class TestFinance(unittest.TestCase):
    def test_zero(self): self.assertEqual(projection(50000,2000,0,12),74000)
    def test_annual(self): self.assertAlmostEqual(projection(50000,0,9,12),54500,places=6)
    def test_initial(self): self.assertEqual(projection(50000,2000,9,0),50000)
    def test_negative(self): self.assertAlmostEqual(projection(100,0,-10,12),90)
