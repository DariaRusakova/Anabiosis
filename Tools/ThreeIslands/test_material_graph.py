"""Regression checks for the material-pin failure in the Windows UE build logs.

Uses a strict API double, not Unreal. In-engine graph/shader checks still run
on the next Windows build.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Content' / 'Python'))
from three_islands_material_graph import connect_nodes, connect_property


class Expression:
    def __init__(self, name, inputs=()):
        self.name, self.inputs = name, inputs

    def get_class(self):
        return self

    def get_name(self):
        return self.name


class MaterialAPI:
    def __init__(self):
        self.connections = []
        self.fail = False

    def get_material_expression_input_names(self, expression):
        return list(expression.inputs)

    def connect_material_expressions(self, source, output, target, pin):
        # Reproduce the log failure: a C++ member called Input does not provide
        # a named graph socket. Empty means the first input in Epic's API.
        if self.fail or not target.inputs or (pin and pin not in target.inputs):
            return False
        self.connections.append((source, output, target, pin))
        return True

    def connect_material_property(self, source, output, material_property):
        if self.fail:
            return False
        self.connections.append((source, output, material_property))
        return True


class MaterialPinRegressionTests(unittest.TestCase):
    def setUp(self):
        self.api = MaterialAPI()
        self.texture = Expression('MaterialExpressionTextureSample')

    def test_desaturation_accepts_unnamed_first_input(self):
        gray = Expression('MaterialExpressionDesaturation', ('', 'Fraction'))
        self.assertFalse(self.api.connect_material_expressions(self.texture, '', gray, 'Input'))
        connect_nodes(self.api, self.texture, gray)
        self.assertEqual(self.api.connections[-1][1::2], ('', ''))

    def test_component_mask_uses_default_input_too(self):
        mask = Expression('MaterialExpressionComponentMask', ('None', 'R', 'G', 'B', 'A'))
        connect_nodes(self.api, self.texture, mask)
        self.assertEqual(self.api.connections[-1][-1], '')

    def test_fraction_keeps_its_second_input(self):
        gray = Expression('MaterialExpressionDesaturation', ('None', 'Fraction', 'LuminanceFactors'))
        connect_nodes(self.api, self.texture, gray, 1)
        self.assertEqual(self.api.connections[-1][-1], 'Fraction')

    def test_later_inputs_are_resolved_from_api(self):
        multiply = Expression('MaterialExpressionMultiply', ('A', 'B (strength)'))
        connect_nodes(self.api, self.texture, multiply, 1)
        self.assertEqual(self.api.connections[-1][-1], 'B (strength)')

    def test_missing_index_fails_before_mutating_graph(self):
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            connect_nodes(self.api, self.texture, Expression('Unary', ('',)), 1)
        self.assertEqual(self.api.connections, [])

    def test_unnamed_secondary_input_cannot_overwrite_first(self):
        with self.assertRaisesRegex(RuntimeError, 'no selectable name'):
            connect_nodes(self.api, self.texture, Expression('Binary', ('A', 'None')), 1)
        self.assertEqual(self.api.connections, [])

    def test_failed_connection_describes_nodes_and_available_inputs(self):
        self.api.fail = True
        with self.assertRaisesRegex(RuntimeError, 'MaterialExpressionTextureSample.*Desaturation.*Fraction'):
            connect_nodes(self.api, self.texture, Expression('Desaturation', ('', 'Fraction')))

    def test_material_property_failure_is_not_ignored(self):
        self.api.fail = True
        with self.assertRaisesRegex(RuntimeError, 'MP_NORMAL'):
            connect_property(self.api, self.texture, '', 'MP_NORMAL')

    def test_material_property_can_use_default_texture_output(self):
        connect_property(self.api, self.texture, '', 'MP_BASE_COLOR')
        self.assertEqual(self.api.connections[-1][1:], ('', 'MP_BASE_COLOR'))


if __name__ == '__main__':
    unittest.main()
