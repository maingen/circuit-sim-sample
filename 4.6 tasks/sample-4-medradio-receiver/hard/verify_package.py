from pathlib import Path
root=Path(__file__).resolve().parent
required=['task.toml','instruction.md','environment/Dockerfile','environment/candidate.cir','tests/Dockerfile','tests/evaluator.py','tests/grade.py','tests/test.sh']
assert all((root/item).is_file() for item in required)
assert 'maingen/sample4-medradio-hard' in (root/'task.toml').read_text()
assert 'private/reference' not in (root/'environment/Dockerfile').read_text()
print('task package checks passed')
