"""Read the one selected installed hash_lookup asset; never write game files.

Uses the existing, pinned DSAR/DSAA reader. Records source chunk checksums,
Steam manifest build and matching loose-patch entries. Does not claim runtime
resource selection or vanilla integrity from the Steam manifest alone.
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
READER=HERE.parent/'voice_tw_integration_20260927'/'extract_baseline.py'
READER_SHA='f20843f72d036b0df0fe28d19c4103985e2a520da04a3a944e0dc51853ea50c2'
TARGET=(0xB9EE36888EF19818,0xE3F2851035957AF5)
PAYLOAD_SHA='3b34c46a17f0aa1003a30cf23a6010c5f08fddcfc5ab9a9020ffd2ef06091557'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:raise ValueError(message)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-data',type=Path,required=True)
    ap.add_argument('--steam-manifest',type=Path,required=True)
    ap.add_argument('--payload',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();require(not a.output.exists(),'refusing manifest overwrite')
    # Payload may already exist from discovery, but it must match exactly.
    require(sha(READER.read_bytes())==READER_SHA,'archive reader changed')
    spec=importlib.util.spec_from_file_location('fixed_archive_reader',READER)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    manifest_raw=a.steam_manifest.read_bytes()
    builds=re.findall(r'"buildid"\s*"(\d+)"',manifest_raw.decode('utf-8'))
    require(builds==['25480438'],'installed Steam manifest build differs')
    catalog=a.game_data/'bundles.nxa'
    catalog_before=sha(catalog.read_bytes())
    archive=mod.BundledArchive(a.game_data)
    files,metadata=mod.archive_files(archive.read)
    require(TARGET in files,'target absent from selected boot archive')
    offset,size=files[TARGET]
    require((offset,size)==(58935280,1048584),'selected resource location changed')
    raw=archive.read(offset,size)
    require(sha(raw)==PAYLOAD_SHA,'selected installed payload changed')
    chunks=[]
    for index,bundle in sorted(archive.bundles.items()):
        for n in sorted(bundle.used_chunks):
            u,c,us,cs,compression,flags,_=bundle.chunks[n]
            with bundle.path.open('rb') as f:f.seek(c);compressed=f.read(cs)
            require(len(compressed)==cs,'truncated source chunk')
            # Re-decode source read a second time to detect a concurrent change.
            repeated=mod.decode_lz4_block(compressed,us) if compression==3 else compressed
            require(repeated==bundle.cache[n],'source chunk changed during extraction')
            chunks.append(dict(bundle=bundle.path.name,chunk=n,uncompressed_offset=u,
                compressed_offset=c,uncompressed_size=us,compressed_size=cs,
                compression=compression,flags=flags,compressed_sha256=sha(compressed),
                decoded_sha256=sha(repeated)))
    patch_scan=[];overrides=[];errors=[]
    for path in sorted(a.game_data.iterdir(),key=lambda p:p.name):
        if not path.is_file() or not re.fullmatch(r'[0-9a-fA-F]{16}\.patch_\d+',path.name):continue
        try:
            with path.open('rb') as f:
                def read(at,n):
                    require(0<=n<=16*1024*1024,'unexpected patch metadata size')
                    f.seek(at);b=f.read(n);require(len(b)==n,'truncated patch');return b
                entries,meta=mod.archive_files(read)
                patch_scan.append(dict(file=path.name,metadata=meta,metadata_sha256=sha(read(0,meta['metadata_size']))))
                if TARGET in entries:
                    at,n=entries[TARGET];b=read(at,n)
                    overrides.append(dict(file=path.name,offset=at,size=n,sha256=sha(b)))
        except (ValueError,IndexError,OSError) as e:
            errors.append(dict(file=path.name,error=str(e)))
    require(sha(catalog.read_bytes())==catalog_before,'catalog changed during extraction')
    require(a.steam_manifest.read_bytes()==manifest_raw,'Steam manifest changed')
    if a.payload.exists():require(a.payload.read_bytes()==raw,'existing output payload differs')
    else:a.payload.write_bytes(raw)
    result=dict(schema_version=1,mode='offline installed asset file read',runtime_verified=False,
        reader=dict(path=str(READER),sha256=READER_SHA),game_data=str(a.game_data),
        steam_manifest=dict(path=str(a.steam_manifest),sha256=sha(manifest_raw),build_id=builds[0]),
        catalog=dict(file='bundles.nxa',sha256=catalog_before),boot_archive=mod.ARCHIVE_NAME,
        archive_metadata=metadata,target_name_hash=f'{TARGET[0]:016x}',target_type_hash=f'{TARGET[1]:016x}',
        payload=dict(file=a.payload.name,offset=offset,size=size,sha256=sha(raw)),source_chunks=chunks,
        loose_patch_scan=patch_scan,matching_loose_overrides=overrides,loose_scan_errors=errors,
        limits=['Selected boot archive plus matching loose patch headers only; not all bundled duplicates or runtime loader priority.',
                'Matching Steam build ID does not prove vanilla files or equality to a currently loaded resource.',
                'No process read, game code execution, patch installation or game-file mutation.'])
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),sha256=sha(a.output.read_bytes()),payload_sha256=sha(raw),source_chunks=len(chunks),loose_patches=len(patch_scan),matching_overrides=len(overrides),scan_errors=len(errors))))


if __name__=='__main__':main()
