from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import subprocess
import pytest
from PIL import Image
from app.media_storage import MediaConfig, MediaError, MARKER, safe_path, image_thumbnail, initialize


def configured(tmp_path):
    root,ops=tmp_path/'media',tmp_path/'ops'
    root.mkdir(); ops.mkdir()
    for folder,kind in ((root,'media'),(ops,'ops')):
        (folder/MARKER).write_text(json.dumps({'environment':'dev','database':'selflore_dev','kind':kind}))
    return MediaConfig(root,ops,'dev','selflore_dev')


def image_bytes(fmt='PNG',size=(20,30)):
    stream=BytesIO(); Image.new('RGB',size,'blue').save(stream,format=fmt); return stream.getvalue()


@pytest.mark.parametrize('fmt',['PNG','JPEG','WEBP'])
def test_original_preserved_and_thumbnail_bounded(tmp_path,fmt):
    config=configured(tmp_path); original=config.root/'source'; thumb=config.root/'thumb.webp'
    content=image_bytes(fmt,(1200,100)); original.write_bytes(content)
    result=image_thumbnail(original,thumb,config)
    assert result['width']==1200
    assert hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256(content).digest()
    with Image.open(thumb) as image:
        assert max(image.size)<=960
        assert not image.getexif()


def test_exif_orientation_and_invalid_images(tmp_path):
    config=configured(tmp_path); original=config.root/'source'; thumb=config.root/'thumb'
    stream=BytesIO(); exif=Image.Exif(); exif[274]=6
    Image.new('RGB',(50,20)).save(stream,'JPEG',exif=exif)
    original.write_bytes(stream.getvalue()); image_thumbnail(original,thumb,config)
    with Image.open(thumb) as image: assert image.size==(20,50)
    original.write_bytes(b'<svg></svg>')
    with pytest.raises(MediaError): image_thumbnail(original,thumb,config)
    original.write_bytes(image_bytes(size=(50,50))); config.max_pixels=100
    with pytest.raises(MediaError,match='像素'): image_thumbnail(original,thumb,config)
    stream=BytesIO(); Image.new('RGB',(3,3)).save(stream,'PNG',save_all=True,append_images=[Image.new('RGB',(3,3),'red')],duration=100)
    original.write_bytes(stream.getvalue()); config.max_pixels=10000
    with pytest.raises(MediaError,match='静态'): image_thumbnail(original,thumb,config)


@pytest.mark.parametrize('key',['../secret','/absolute','a/../x','a\\b','C:/secret'])
def test_paths_cannot_escape(tmp_path,key):
    config=configured(tmp_path)
    with pytest.raises(MediaError): safe_path(config.root,key)


def test_no_implicit_creation_or_identity_repair(tmp_path):
    config=MediaConfig(tmp_path/'missing',tmp_path/'ops','dev','selflore_dev')
    with pytest.raises(MediaError): config.check()
    assert not config.root.exists()
    config=configured(tmp_path)
    (config.root/MARKER).write_text('{}')
    with pytest.raises(MediaError): config.check()
    assert (config.root/MARKER).read_text()=='{}'


def test_explicit_initialization_and_limits(tmp_path):
    config=MediaConfig(tmp_path/'media',tmp_path/'ops','dev','selflore_dev')
    initialize(config)
    assert config.check()==config.root and config.check(ops=True)==config.ops_root
    assert (config.ops_root/'telemetry.lock').read_bytes()==b'0'
    initialize(config)
    original=config.root/'source'; original.write_bytes(image_bytes(size=(50,20)))
    config.max_edge=40
    with pytest.raises(MediaError,match='最长边'): image_thumbnail(original,config.root/'thumb',config)


def test_directory_link_is_rejected_before_reading(tmp_path):
    config=configured(tmp_path); outside=tmp_path/'outside'; outside.mkdir()
    (outside/'private').write_text('synthetic external content')
    link=config.root/'linked'
    if os.name=='nt':
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                        'New-Item -ItemType Junction -Path $env:SELFLORE_TEST_LINK -Target $env:SELFLORE_TEST_LINK_TARGET | Out-Null'],
                       env={**os.environ,'SELFLORE_TEST_LINK':str(link),'SELFLORE_TEST_LINK_TARGET':str(outside)},check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:
        link.symlink_to(outside,target_is_directory=True)
    with pytest.raises(MediaError,match='链接|重解析'):
        safe_path(config.root,'linked/private')


def test_explicit_portable_initializer_records_selected_environment(tmp_path):
    from app.media_storage import main
    root,ops=tmp_path/'portable-media',tmp_path/'portable-ops'
    assert main(['--initialize','--environment','prod','--media-root',str(root),'--ops-root',str(ops)])==0
    assert json.loads((root/MARKER).read_text())=={'environment':'prod','database':'selflore_prod','kind':'media'}
    assert main(['--initialize','--environment','dev','--media-root',str(root),'--ops-root',str(ops)])==1
    assert json.loads((root/MARKER).read_text())['environment']=='prod'
