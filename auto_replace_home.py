# -*- coding: utf-8 -*-
"""
Home Illustration Replace - Automated Pipeline
Automates the full 4-step workflow:
1. Decrypt material bundle from input/ into hometool/
2. Patch bundle ID via hometool/patch_home_illustration_skel.py
3. Extract target bundle from game dat, overwrite with patched bundle, and re-encrypt
4. Copy final encrypted bundle to output/ and clean temporary files
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Safe console output for Windows GBK/UTF-8 environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        try:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        except Exception:
            pass


def clear_directory(path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except OSError:
                pass


def clear_az_workdirs(az_dir: Path):
    for name in ["bak", "decrypt", "encrypt", "export", "source"]:
        clear_directory(az_dir / name)


def copy_directory_contents(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)


class BydRunner:
    def __init__(self, az_dir: Path):
        self.az_dir = az_dir
        self.exe_path = az_dir / "byd_mod_studio.exe"
        if not self.exe_path.exists():
            raise FileNotFoundError(f"byd_mod_studio.exe 未在 {az_dir} 中找到！")

    def run_step1_material_decrypt(self) -> int:
        """Run byd_mod_studio to decrypt input material bundles."""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        proc = subprocess.Popen(
            [str(self.exe_path)],
            cwd=str(self.az_dir),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        def read_until(pattern: str, timeout: float = 60.0) -> str:
            buf = ""
            start = time.time()
            while time.time() - start < timeout:
                if proc.poll() is not None:
                    break
                ch = proc.stdout.read(1)
                if ch:
                    buf += ch
                    if pattern in buf:
                        return buf
                else:
                    time.sleep(0.02)
            if pattern not in buf:
                raise TimeoutError(f"等待提示 '{pattern}' 超时: {buf[-300:]}")
            return buf

        try:
            # Step 0: copy files from dat path? -> n
            read_until("copy files from dat path into source folder")
            proc.stdin.write("n\n")
            proc.stdin.flush()

            # Step 1: decrypt original bundles? -> enter (default Y)
            read_until("decrypt original bundles")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Press <Enter> when ready...
            read_until("when ready")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Wait for decryption to complete (step 2 prompt appears)
            read_until("export textures", timeout=120.0)
            log("素材解密完成，关闭 byd_mod_studio 窗口...")

            # 解密完成后直接终止进程
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except Exception as e:
            if proc.poll() is None:
                proc.kill()
            raise e

        return 0

    def run_step3_target_replace_encrypt(self, processed_file: Path, decrypt_dir: Path) -> int:
        """Run byd_mod_studio to copy target from dat, decrypt, overwrite with processed, and encrypt."""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        proc = subprocess.Popen(
            [str(self.exe_path)],
            cwd=str(self.az_dir),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        def read_until(pattern: str, timeout: float = 60.0) -> str:
            buf = ""
            start = time.time()
            while time.time() - start < timeout:
                if proc.poll() is not None:
                    break
                ch = proc.stdout.read(1)
                if ch:
                    buf += ch
                    if pattern in buf:
                        return buf
                else:
                    time.sleep(0.02)
            if pattern not in buf:
                raise TimeoutError(f"等待提示 '{pattern}' 超时: {buf[-300:]}")
            return buf

        try:
            # Step 0: copy files from dat path? -> enter (default Y)
            read_until("copy files from dat path into source folder")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Step 1: decrypt original bundles? -> enter (default Y)
            read_until("decrypt original bundles")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Press <Enter> when ready...
            read_until("when ready")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Wait for decryption to complete (step 2 prompt appears)
            read_until("export textures", timeout=120.0)
            log("目标主界面立绘解密完成，正在用处理后的文件覆盖 AZ/decrypt...")

            # Overwrite matching file in AZ/decrypt
            target_decrypt_file = decrypt_dir / processed_file.name
            shutil.copy2(processed_file, target_decrypt_file)
            log(f"成功覆盖: {target_decrypt_file.name}")

            # Step 2: export textures? -> n
            proc.stdin.write("n\n")
            proc.stdin.flush()

            # Step 3: import edited textures? -> n
            read_until("import edited textures")
            proc.stdin.write("n\n")
            proc.stdin.flush()

            # Step 4: re-encrypt bundles? -> enter (default Y)
            read_until("re-encrypt bundles")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Press <Enter> to re-encrypt...
            read_until("to re-encrypt")
            proc.stdin.write("\n")
            proc.stdin.flush()

            # Wait for encryption to complete
            out, err = proc.communicate(timeout=120.0)
            if proc.returncode != 0:
                raise RuntimeError(f"byd_mod_studio 异常退出，退出码: {proc.returncode}: {err}")
            log("封包重新加密完成！")
        except Exception as e:
            if proc.poll() is None:
                proc.kill()
            raise e

        return 0


def update_source_txt(source_txt_path: Path, target_id: str):
    new_line = f"Prefabs/UI/HomeIllustration/hi_{target_id}\n"
    source_txt_path.write_text(new_line, encoding="utf-8")
    log(f"已更新 source.txt -> Prefabs/UI/HomeIllustration/hi_{target_id}")


def run_pipeline(
    base_dir: Path,
    target_id: str,
    keep_input: bool = False,
    keep_temp: bool = False,
):
    log("=" * 60)
    log(f"开始主界面立绘一键替换流程: 目标立绘ID [{target_id}]")
    log("=" * 60)

    az_dir = base_dir / "AZ"
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    hometool_dir = base_dir / "hometool"
    temp_dir = base_dir / "tempdata"

    az_source = az_dir / "source"
    az_decrypt = az_dir / "decrypt"
    az_encrypt = az_dir / "encrypt"
    az_source_txt = az_dir / "source.txt"
    az_dat_path_txt = az_dir / "dat_path.txt"

    patch_script = hometool_dir / "patch_home_illustration_skel.py"

    # Pre-flight checks
    if not input_dir.exists() or not any(input_dir.rglob("*")):
        raise FileNotFoundError(f"[ERROR] input 文件夹为空: {input_dir}\n请将主界面立绘素材放入 input 文件夹后再运行！")

    if not az_dat_path_txt.exists():
        raise FileNotFoundError(f"[ERROR] dat_path.txt 未找到: {az_dat_path_txt}")

    dat_path = Path(az_dat_path_txt.read_text(encoding="utf-8").strip())
    if not dat_path.exists():
        raise FileNotFoundError(f"[ERROR] 游戏 dat 路径不存在: {dat_path}，请检查 AZ/dat_path.txt！")

    if not patch_script.exists():
        raise FileNotFoundError(f"[ERROR] 素材处理脚本未找到: {patch_script}")

    runner = BydRunner(az_dir)

    # ----------------------------------------------------
    # 步骤 1: 解密素材
    # ----------------------------------------------------
    log("[步骤 1/4] 清空 output 与工作目录，准备解密素材...")
    clear_directory(output_dir)
    clear_directory(temp_dir)
    clear_az_workdirs(az_dir)

    log("复制 input 中的素材到 AZ/source...")
    copy_directory_contents(input_dir, az_source)

    log("启动 byd_mod_studio 解密素材...")
    runner.run_step1_material_decrypt()

    decrypted_files = [f for f in az_decrypt.glob("Prefabs_UI_HomeIllustration_hi_*") if f.is_file()]
    if not decrypted_files:
        raise RuntimeError("[ERROR] AZ/decrypt 中未生成解密文件，请检查素材文件与清单！")

    material_file = decrypted_files[0]
    log(f"成功解密素材文件: {material_file.name}")

    # 复制到 hometool 中
    hometool_material = hometool_dir / material_file.name
    shutil.copy2(material_file, hometool_material)
    log(f"已复制到 hometool: {hometool_material.name}")

    # 清理 AZ 工作目录
    log("清理 AZ 工作目录...")
    clear_az_workdirs(az_dir)

    # ----------------------------------------------------
    # 步骤 2: 执行素材 ID 替换处理
    # ----------------------------------------------------
    log(f"[步骤 2/4] 执行素材处理: 目标 ID -> {target_id}...")
    cmd = [
        sys.executable,
        str(patch_script),
        target_id,
        "--target",
        str(hometool_material),
        "--overwrite",
    ]
    res = subprocess.run(cmd, cwd=str(hometool_dir))
    if res.returncode != 0:
        raise RuntimeError(f"[ERROR] patch_home_illustration_skel.py 处理失败，退出码: {res.returncode}")

    processed_file = hometool_dir / f"Prefabs_UI_HomeIllustration_hi_{target_id}"
    if not processed_file.exists():
        raise FileNotFoundError(f"[ERROR] 未在 hometool 中生成处理后文件: {processed_file.name}")

    log(f"素材处理完成，已生成目标立绘文件: {processed_file.name}")

    # ----------------------------------------------------
    # 步骤 3: 目标立绘提取、覆盖与重加密
    # ----------------------------------------------------
    log(f"[步骤 3/4] 更新 AZ/source.txt 为目标立绘编号 {target_id}...")
    update_source_txt(az_source_txt, target_id)

    log("启动 byd_mod_studio 从 dat 提取目标立绘、覆盖并重新封包加密...")
    runner.run_step3_target_replace_encrypt(processed_file, az_decrypt)

    # ----------------------------------------------------
    # 步骤 4: 收尾与输出
    # ----------------------------------------------------
    log("[步骤 4/4] 导出最终成果到 output 文件夹并清理...")
    encrypted_files = list(az_encrypt.glob("*"))
    if not encrypted_files:
        raise RuntimeError("[ERROR] AZ/encrypt 中没有生成加密文件！")

    copy_directory_contents(az_encrypt, output_dir)
    log(f"成果已成功保存至 output: {output_dir}")

    # 清理 AZ 工作目录
    log("清理 AZ 工作目录...")
    clear_az_workdirs(az_dir)

    # 清除 hometool 中的临时文件
    if not keep_temp:
        log("清理 hometool 中的中间素材与处理文件...")
        if hometool_material.exists():
            try:
                hometool_material.unlink()
                log(f"  已删除临时文件: {hometool_material.name}")
            except OSError:
                pass
        if processed_file.exists():
            try:
                processed_file.unlink()
                log(f"  已删除临时文件: {processed_file.name}")
            except OSError:
                pass
        clear_directory(temp_dir)
    else:
        log("[保留] hometool 中间文件未删除。")

    # 清理 input
    if not keep_input:
        log("清空 input 素材文件夹...")
        clear_directory(input_dir)
    else:
        log("[保留] input 素材未删除。")

    out_files = [f for f in output_dir.rglob("*") if f.is_file()]
    log("=" * 60)
    log(f"[SUCCESS] 全部流程执行成功！共生成 {len(out_files)} 个主界面立绘加密 Mod 文件。")
    for f in out_files:
        log(f"  成品: {f.relative_to(output_dir)} ({f.stat().st_size:,} 字节)")
    log(f"输出目录: {output_dir}")
    log("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="主界面立绘一键自动化替换工具")
    parser.add_argument("target_id", nargs="?", help="目标立绘编号 (例如 1005)")
    parser.add_argument("--target-id", dest="target_id_opt", help="目标立绘编号 (例如 1005)")
    parser.add_argument("--keep-input", action="store_true", help="保留 input 素材文件夹")
    parser.add_argument("--keep-temp", action="store_true", help="保留中间临时文件")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent

    target_id = args.target_id or args.target_id_opt

    if not target_id:
        target_id = input("请输入目标素材的编号 (例如 1005): ").strip()

    if not target_id or not target_id.isdigit():
        print("[ERROR] 目标立绘编号必须全为数字！", file=sys.stderr)
        sys.exit(1)

    try:
        run_pipeline(
            base_dir=base_dir,
            target_id=target_id,
            keep_input=args.keep_input,
            keep_temp=args.keep_temp,
        )
    except Exception as e:
        log(f"[ERROR] 流程执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
