"""Compile actual GPIO patch callbacks and kill swallowed write errors."""
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'phone/kernel/patches/0003-apple-gpio-write-errors.patch'
METHODS = ('apple_gpio_set_reg', 'apple_gpio_pinmux_set', 'apple_gpio_set',
           'apple_gpio_direction_input', 'apple_gpio_direction_output',
           'apple_gpio_irq_type', 'apple_gpio_irq_set_type')


def function(source, name):
    matches = list(re.finditer(r'static (?:int|void|unsigned int) ' + re.escape(name)
                              + r'\([^;{}]*\)\n\{', source))
    if len(matches) != 1:
        raise ValueError('Function identity differs: ' + name)
    start = matches[0].start()
    end = matches[0].end()
    depth = 1
    while end < len(source) and depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('Incomplete patch function: ' + name)
    return source[start:end]


def patch_source(*, original=False):
    lines = PATCH.read_text().splitlines()
    target = 'drivers/pinctrl/pinctrl-apple-gpio.c'
    if lines[:2] != ['--- a/' + target, '+++ b/' + target]:
        raise ValueError('Unexpected patch target.')
    prefix = (' ', '-') if original else (' ', '+')
    source = '\n'.join(line[1:] for line in lines[2:] if line.startswith(prefix))
    return '\n\n'.join(function(source, name) for name in METHODS) + '\n'


def mutation(source, method, before, after):
    original = function(source, method)
    if original.count(before) != 1:
        raise ValueError('Mutation anchor differs: ' + method)
    return source.replace(original, original.replace(before, after, 1), 1)


def mutations(source):
    yield 'helper-swallowed-error', mutation(
        source, 'apple_gpio_set_reg',
        'return regmap_update_bits(pctl->map, REG_GPIO(pin), mask, value);',
        'regmap_update_bits(pctl->map, REG_GPIO(pin), mask, value); return 0;')
    for method in METHODS[1:5]:
        original = function(source, method)
        altered = original.replace('return apple_gpio_set_reg(', 'apple_gpio_set_reg(', 1)
        if altered == original:
            raise ValueError('Missing callback return: ' + method)
        altered = altered[:-1] + '\treturn 0;\n}'
        yield 'swallowed-' + method, source.replace(original, altered, 1)
    yield 'irq-swallowed-error', mutation(source, 'apple_gpio_irq_set_type',
                                          'if (ret)\n\t\treturn ret;',
                                          'if (ret)\n\t\treturn 0;')
    yield 'irq-handler-after-error', mutation(source, 'apple_gpio_irq_set_type',
                                              'if (ret)\n\t\treturn ret;', '(void)ret;')
    yield 'irq-invalid-success', mutation(source, 'apple_gpio_irq_set_type',
                                          'return -EINVAL;', 'return 0;')
    yield 'pin-offset-wrong', mutation(source, 'apple_gpio_set_reg',
                                       'REG_GPIO(pin)', 'REG_GPIO(pin + 1)')
    yield 'mux-missing-input', mutation(source, 'apple_gpio_pinmux_set',
                                        'FIELD_PREP(REG_GPIOx_PERIPH, func) | REG_GPIOx_INPUT_ENABLE',
                                        'FIELD_PREP(REG_GPIOx_PERIPH, func)')
    yield 'input-clobbers-other-bits', mutation(
        source, 'apple_gpio_direction_input',
        'REG_GPIOx_PERIPH | REG_GPIOx_MODE | REG_GPIOx_DATA |',
        'REG_GPIOx_PERIPH | REG_GPIOx_MODE | REG_GPIOx_DATA | BIT(21) |')


class GPIOWriteErrorTests(unittest.TestCase):
    def test_actual_callbacks_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        source = patch_source()
        with tempfile.TemporaryDirectory(prefix='n71-gpio-errors-') as directory:
            folder = Path(directory)
            binary = folder / 'contract'
            variants = [('baseline', source), ('original-regression', patch_source(original=True))]
            variants += list(mutations(source))
            completed = 0
            for name, modified in variants:
                with self.subTest(name=name):
                    (folder / 'n71-gpio-provider-functions.h').write_text(modified)
                    built = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_gpio_write_errors.c'),
                         '-o', str(binary)], capture_output=True, text=True, timeout=30,
                        env=dict(os.environ, LC_ALL='C'))
                    self.assertEqual(built.returncode, 0,
                                     'Compilation error is not mutation proof: ' + built.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True,
                                            cwd=folder, timeout=20, env=dict(os.environ, LC_ALL='C'))
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_GPIO_WRITE_ERRORS_OK cases=816', result.stdout)
                        print(result.stdout.strip(), flush=True)
                    else:
                        self.assertEqual(result.returncode, -signal.SIGABRT, result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_GPIO_WRITE_ERRORS_ASSERTION_KILL ' + name, flush=True)
                    completed += 1
            self.assertEqual(completed, len(variants), 'No gate success after any failed subtest')
        print('N71_GPIO_WRITE_ERRORS_MUTATION_GATE_OK 11', flush=True)


if __name__ == '__main__':
    unittest.main()
