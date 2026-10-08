# 影之诗主界面立绘一键自动化替换工具

本工具将原先需要多步手动打开/关闭程序、复制粘贴文件、输入步骤指令的主界面立绘（HomeIllustration）替换流程，封装为**一键全自动执行**。

---

## 目录结构说明

- `input/`：放置提取好的主界面立绘素材（1个文件，支持带子目录如 `KL\xxxx` 或直接散装）。
- `output/`：最终生成的加密 Mod 文件（1个文件），可直接放回游戏 `dat` 路径生效。
- `tempdata/`：自动处理过程中的临时工作区（流程结束后自动清理）。
- `AZ/`：包含 `byd_mod_studio.exe` 及辅助解密加密工具与清单文件。
- `hometool/`：包含 `patch_home_illustration_skel.py`，负责立绘骨骼、文本、CAB 及 ID 的深度转换。
- `一键替换主界面立绘.bat`：双击直接运行的用户交互批处理入口。
- `auto_replace_home.py`：负责全流程自动化驱动与进程管道交互的 Python 核心。

---

## 使用方法

### 方式一：双击运行（最简便）
1. 将主界面立绘素材放入 `input/` 文件夹。
2. 双击运行 `一键替换主界面立绘.bat`（或 `auto_replace_home.bat`）。
3. 根据提示输入：
   - **目标立绘编号**（例如：`1005`）
4. 工具会自动在数秒内完成全部解密、ID转换、从游戏提取目标底模、覆盖、重新封包加密，并清空临时文件。
5. 完成后到 `output/` 文件夹取走成果即可。

### 方式二：命令行传参运行
也可以直接带参数调用批处理或 Python 脚本，无需交互输入：
```cmd
一键替换主界面立绘.bat 1005
```
或
```cmd
python auto_replace_home.py 1005
```

可选参数：
- `--keep-input`：处理完成后不删除 `input/` 中的素材。
- `--keep-temp`：处理完成后不清理 `hometool/` 中的中间文件（用于调试排查）。

---

## 自动化执行流程

1. **Step 1 - 解密素材**：清空工作区，将 `input` 素材放入 `AZ/source`，驱动 `byd_mod_studio.exe` 解密得到原始立绘文件（例如 `Prefabs_UI_HomeIllustration_hi_105741202`），复制到 `hometool/` 待用，并清理 `AZ`。
2. **Step 2 - 素材转换**：调用 `patch_home_illustration_skel.py` 自动识别素材旧编号，并替换为目标编号（例如 `1005`），完成骨骼、文本、MonoBehaviour typetree 和 CAB 的深度重写与校验。
3. **Step 3 - 目标提取与重加密**：自动更新 `AZ/source.txt` 为目标立绘编号，从游戏 `dat` 中提取目标立绘原文件并解密，使用处理后的素材自动覆盖，随后驱动 `byd_mod_studio.exe` 完成加密封包。
4. **Step 4 - 导出与收尾**：将生成的最终加密文件转移至 `output/`，自动清理 `AZ` 工作区、清空 `input` 及 `hometool` 中的临时文件。
