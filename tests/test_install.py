"""Run install.py against temporary Cider profiles."""
import importlib.util
import json
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / 'install.py'


def test_installer_temporary_profile_backup_and_no_asset_secret(tmp_path,capsys):
    source=INSTALLER
    spec=importlib.util.spec_from_file_location('fu38_installer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    profile=tmp_path/'profile';secret=tmp_path/'config/key'
    import hashlib,shutil
    staged=tmp_path/'source';shutil.copytree(source.parent,staged)
    module.SOURCE=staged
    assets=tmp_path/'assets';assets.mkdir()
    (assets/'fixture.js').write_text('offline asset')
    (staged/'host-assets.json').write_text(json.dumps({'fixture.js':hashlib.sha256((assets/'fixture.js').read_bytes()).hexdigest()}))
    module.install(profile,secret,10768,assets)
    target=profile/'plugins'/module.IDENTIFIER
    value=secret.read_text().strip()
    assert value not in (target/'connection.mjs').read_text()
    (target/'existing-file').write_text('keep me')
    module.install(profile,secret,10768,assets)
    backups=list((profile/'podbox-backups').iterdir())
    assert len(backups)==1 and (backups[0]/'existing-file').read_text()=='keep me'
    assert secret.stat().st_mode&0o777==0o600
    assert value not in capsys.readouterr().out
    with pytest.raises(FileNotFoundError):module.install(profile,secret,10768,tmp_path/'wrong-assets')


def test_installer_prefers_active_ota_and_rejects_changed_bytes(tmp_path):
    import hashlib,shutil,zipfile
    source=INSTALLER
    spec=importlib.util.spec_from_file_location('fu38_ota_installer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    staged=tmp_path/'source';shutil.copytree(source.parent,staged);module.SOURCE=staged
    profile=tmp_path/'profile';profile.mkdir();secret=tmp_path/'secret'
    raw=b'known active renderer entry'
    (staged/'host-assets.json').write_text(json.dumps({'index-fixture.js':hashlib.sha256(raw).hexdigest()}))
    with zipfile.ZipFile(profile/'update.cup','w') as z:z.writestr('spa/assets/index-fixture.js',raw)
    module.install(profile,secret,10768)
    target=profile/'plugins'/module.IDENTIFIER
    assert (target/'renderer.mjs').exists()
    assert 'index-fixture.js' in (target/'connection.mjs').read_text()
    with zipfile.ZipFile(profile/'update.cup','w') as z:z.writestr('spa/assets/index-fixture.js',b'changed')
    before=(target/'plugin.js').read_bytes()
    with pytest.raises(ValueError,match='Unsupported Cider'):module.install(profile,secret,10768)
    assert (target/'plugin.js').read_bytes()==before
    assert not (profile/'podbox-backups').exists()
