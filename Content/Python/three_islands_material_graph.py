"""Material connections using UE's actual pin names; no engine import needed."""


def connect_nodes(library, source, target, input_index=0, output_name=''):
    """An empty target name selects input 0, including unnamed unary pins.

    C++ member names such as Desaturation.Input need not be graph pin labels.
    Resolve every later input through the live MaterialEditingLibrary instead
    of assuming labels such as Fraction, A, B or Coordinates.
    """
    names = list(library.get_material_expression_input_names(target))
    if not isinstance(input_index, int) or not 0 <= input_index < len(names):
        raise RuntimeError(f'Material input index {input_index!r} is unavailable; inputs={names!r}')
    pin_name = '' if input_index == 0 else str(names[input_index])
    if input_index > 0 and (not pin_name or pin_name.casefold() == 'none'):
        raise RuntimeError(f'Material input {input_index} has no selectable name; inputs={names!r}')
    if not library.connect_material_expressions(source, output_name, target, pin_name):
        raise RuntimeError(
            f'Cannot connect {source.get_class().get_name()} output {output_name!r} '
            f'to {target.get_class().get_name()} input {input_index} ({pin_name!r}); '
            f'available inputs={names!r}')


def connect_property(library, source, output_name, material_property):
    if not library.connect_material_property(source, output_name, material_property):
        raise RuntimeError(
            f'Cannot connect {source.get_class().get_name()} output {output_name!r} '
            f'to material property {material_property}')
