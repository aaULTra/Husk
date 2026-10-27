#!/usr/bin/env python3
"""Execute3.1 resource staging and actual Swift bundle import with protected defaults."""
import hashlib,importlib.util,io,json,os,shutil,struct,subprocess,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('stage',ROOT/'scripts/stage_graphics_build.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
class StagingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
  self.old=(stage.ROOT,stage.SHA256,stage.QEMU_BASE_SHA256);self.addCleanup(self.restore);stage.ROOT=self.p
  project=self.p/'src/app/project.yml';project.parent.mkdir(parents=True);project.write_text('dependency: ../../build/ios-arm64/lib/MoltenVK.xcframework\n    preBuildScripts:\n      old\n    postBuildScripts:\n      retained\n')
  self.new=self.p/'new.ipa';self.old_ipa=self.p/'old.ipa'
  with zipfile.ZipFile(self.new,'w') as z:
   for name in ['libqemu-aarch64-softmmu.dylib','libANGLE-shared.dylib','libhuskps4.dylib','MoltenVK.framework/MoltenVK']:z.writestr('Payload/Husk.app/Frameworks/'+name,b'new-'+name.encode())
   z.writestr('Payload/Husk.app/java-runtime/husk-framework.dex',b'3.1-java');z.writestr('Payload/Husk.app/Husk',b'donor-executable')
  with zipfile.ZipFile(self.old_ipa,'w')as z:z.writestr('Payload/Husk.app/Frameworks/libqemu-aarch64-softmmu.dylib',b'protected-qemu')
  stage.SHA256=hashlib.sha256(self.new.read_bytes()).hexdigest();stage.QEMU_BASE_SHA256=hashlib.sha256(self.old_ipa.read_bytes()).hexdigest()
 def restore(self):stage.ROOT,stage.SHA256,stage.QEMU_BASE_SHA256=self.old
 def test_matching_resources_and_protected_qemu_are_staged(self):
  stage.stage(self.new,self.old_ipa)
  self.assertEqual((self.p/'build/ios-arm64/lib/libqemu-aarch64-softmmu.dylib').read_bytes(),b'protected-qemu')
  self.assertEqual((self.p/'build/graphics-base/Payload/Husk.app/java-runtime/husk-framework.dex').read_bytes(),b'3.1-java')
  project=(self.p/'src/app/project.yml').read_text();self.assertIn('--exclude=Husk ',project);self.assertIn('postBuildScripts:\n      retained',project)
 def test_wrong_primary_release_is_rejected_before_staging(self):
  stage.SHA256='0'*64
  with self.assertRaises(SystemExit):stage.stage(self.new,self.old_ipa)
  self.assertFalse((self.p/'build').exists())
 def test_wrong_qemu_baseline_is_rejected_before_staging(self):
  stage.QEMU_BASE_SHA256='0'*64
  with self.assertRaises(SystemExit):stage.stage(self.new,self.old_ipa)
  self.assertFalse((self.p/'build').exists())

@unittest.skipUnless(shutil.which('swiftc'),'Apple Swift/Compression unavailable locally; required IPA CI executes importer')
class BundleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);p=Path(cls.tmp.name);cls.p=p
  (p/'main.swift').write_text('''import Foundation
let input=URL(fileURLWithPath:CommandLine.arguments[1]),output=URL(fileURLWithPath:CommandLine.arguments[2])
do { let names=try BundleUnpacker.unpack(input,into:output);for name in names { print(name) } }
catch { fputs("rejected\\n",stderr);exit(2) }
''');cls.exe=p/'unpack';subprocess.run(['swiftc',str(ROOT/'src/app/Husk/ApkMetadata.swift'),str(ROOT/'src/app/Husk/BundleUnpacker.swift'),str(p/'main.swift'),'-o',str(cls.exe)],check=True)
 def unpack(self,data,success=True):
  with tempfile.TemporaryDirectory(dir=self.p)as d:
   p=Path(d);src=p/'test.xapk';src.write_bytes(data);out=p/'output';out.mkdir();r=subprocess.run([str(self.exe),str(src),str(out)],capture_output=True,text=True,timeout=10)
   self.assertEqual(r.returncode,0 if success else 2,r.stderr)
   return {str(f.relative_to(out)):f.read_bytes()for f in out.rglob('*')if f.is_file()},r.stdout.splitlines()
 def test_stored_and_deflated_apks_and_obb_stream_correctly(self):
  for method in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
   b=io.BytesIO();data=b'apk-bytes'*20000;obb=b'obb-bytes'*40000
   with zipfile.ZipFile(b,'w',compression=method)as z:z.writestr('base.apk',data);z.writestr('Android/obb/com.example/main.1.com.example.obb',obb)
   files,names=self.unpack(b.getvalue());self.assertEqual(files,{'base.apk':data,'obb/main.1.com.example.obb':obb});self.assertEqual(set(names),set(files))
 @staticmethod
 def zip64():
  name=b'base.apk';data=b'zip64-payload';crc=__import__('zlib').crc32(data)
  local=struct.pack('<I5H3I2H',0x04034b50,45,0,0,0,0,crc,len(data),len(data),len(name),0)+name+data
  extra=struct.pack('<HHQQQ',1,24,len(data),len(data),0)
  central=struct.pack('<I6H3I5H2I',0x02014b50,45,45,0,0,0,0,crc,0xffffffff,0xffffffff,len(name),len(extra),0,0,0,0,0xffffffff)+name+extra
  record=struct.pack('<IQ2H2I4Q',0x06064b50,44,45,45,0,0,1,1,len(central),len(local));locator=struct.pack('<IIQI',0x07064b50,0,len(local)+len(central),1);end=struct.pack('<I4H2IH',0x06054b50,0,0,0xffff,0xffff,0xffffffff,0xffffffff,0)
  return local+central+record+locator+end
 def test_zip64_sentinel_sizes_are_read_from_valid_extras(self):
  files,names=self.unpack(self.zip64());self.assertEqual(files,{'base.apk':b'zip64-payload'})
 def test_oversized_zip64_directory_is_rejected_without_integer_trap(self):
  b=bytearray(self.zip64());p=b.index(b'PK\x06\x06');struct.pack_into('<Q',b,p+40,0xffffffffffffffff);self.unpack(b,False)
 def test_truncated_zip64_extra_is_rejected_without_bounds_trap(self):
  b=bytearray(self.zip64());p=b.index(b'PK\x01\x02');extra=p+46+len('base.apk');struct.pack_into('<H',b,extra+2,65535);self.unpack(b,False)
if __name__=='__main__':unittest.main()
