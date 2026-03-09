import json
import unittest
import ProViBackend.FilterModel.OldFilter as Filter


class FilterTest(unittest.TestCase):
    def test_svg_mapping(self):
        # Arrange
        # Act
        Filter.create_all_subplots(r"C:\Users\frede\Documents\Uni_Mannheim\Master\02_Semester\TeamProject\ProViBackend\tests\testdata\NoNoise.xes",
                                r'C:\Users\frede\Documents\Uni_Mannheim\Master\02_Semester\TeamProject\ProViBackend\tests\tmp/')
        # Assert
        with open(r"C:\Users\frede\Documents\Uni_Mannheim\Master\02_Semester\TeamProject\ProViBackend\tests\testdata\test_mapping.json", "r") as left:
            left_mapping = json.load(left)
        with open(r"C:\Users\frede\Documents\Uni_Mannheim\Master\02_Semester\TeamProject\ProViBackend\tests\tmp\mapping.json", "r") as right:
            right_mapping = json.load(right)
        self.assertEqual(left_mapping, right_mapping)


if __name__ == '__main__':
    unittest.main()
