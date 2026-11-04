# 代码签名与 SmartScreen

## 提示是怎么来的

Windows 会给“从网络下载”的文件打上 Mark-of-the-Web（MotW，即 Zone.Identifier 备用数据流）。带 MotW 的可执行文件在启动时会经过 Microsoft Defender SmartScreen：

- 没有签名，或签名证书没有足够声誉 → “Windows 已保护你的电脑”，需要“更多信息 → 仍要运行”；
- 有受信任且声誉良好的签名 → 直接运行，发布者显示为证书主体。

因此同一个 exe，本机自己构建、自己双击不会提示；用户从 Releases 下载后才会提示。这不是程序本身的问题，签名只能缓解、不能改变“新文件没有声誉”这一事实。

## 不签名时的三种处理

1. 提示框里点“更多信息”，再点“仍要运行”。
2. 右键 exe → 属性 → 常规页底部勾选“解除锁定” → 确定；之后双击不再提示（MotW 被移除）。
3. PowerShell 批量解除：

   ```powershell
   Get-ChildItem -Path . -Recurse -Include *.exe,*.zip | Unblock-File
   ```

   建议先解压 zip 再对 exe 解除锁定；对 zip 解除锁定后再解压同样有效。

## 彻底消除提示：受信任的代码签名证书

| 方案 | 费用 | 周期与门槛 | SmartScreen 效果 | 适合 |
| --- | --- | --- | --- | --- |
| 自签名证书 | 免费 | 立即 | 对方导入并信任证书后可用；对外分发仍会提示 | 内网、自己机器 |
| OV 代码签名证书 | 约 ¥1000–3000/年（以 CA 报价为准） | 1–5 个工作日，需实名/企业资料 | 证书受信任，但新证书仍需积累下载声誉，提示逐步消失 | 常规对外分发 |
| EV 代码签名证书 | 更高，通常配硬件 token | 数天，需企业资质 | 一般可立即获得较高声誉，基本不再提示 | 商业分发 |
| Azure Artifact Signing（原 Trusted Signing） | 订阅制，Basic 档约 $10/月 | 需 Azure 订阅并通过身份验证 | 证书受信任，声誉逐步积累 | CI 云签名 |
| SignPath Foundation | 开源项目免费 | 需项目审核 | 由基金会证书签名，受信任 | 公开开源项目 |

本项目是公开开源仓库，**SignPath Foundation** 是最省钱的路径：它校验“二进制确实由该仓库构建”，私钥保存在 HSM，并提供 GitHub Actions 集成。如果想立刻消除提示，则选 EV。

## 仓库内置的签名流程

证书拿到后，一条命令完成“构建 → 签名 → 打包 → 生成校验值”：

```powershell
$env:ZSIGN_PFX_PASSWORD = "你的pfx密码"   # 避免密码出现在命令行历史里
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipInstall -Sign -PfxPath C:\keys\zhao.pfx
```

证书已装在当前用户证书存储时，改用指纹：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipInstall -Sign -CertThumbprint 1A2B3C...
```

只签名一个已存在的 exe：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\sign.ps1 -Path dist\ZhaoZhaoRecord.exe -PfxPath C:\keys\zhao.pfx
```

要点：

- 签名发生在压缩 zip 之前，所以 zip 与 `dist\SHA256SUMS.txt` 都对应签名后的 exe。
- 优先调用 `signtool.exe`（Windows SDK），参数为 SHA-256 + RFC 3161 时间戳（默认 `http://timestamp.digicert.com`）。
- 找不到 signtool 时回退到 PowerShell `Set-AuthenticodeSignature`；PFX 以 `EphemeralKeySet` 在内存中加载，不写入证书存储、也不会误删同名证书。
- 离线环境可加 `-TimestampUrl none` 跳过时间戳，但发布版不建议这样做——没有时间戳，证书过期后已发布的签名会失效。

## 验证签名

```powershell
Get-AuthenticodeSignature dist\ZhaoZhaoRecord.exe | Format-List Status, StatusMessage, SignerCertificate, TimeStamperCertificate
```

`Status` 应为 `Valid`，且 `TimeStamperCertificate` 不为空。也可用 `signtool verify /pa /v dist\ZhaoZhaoRecord.exe`。

## 接入 CI（可选）

PFX 以 Base64 存入仓库 Secrets（`PFX_BASE64`、`PFX_PASSWORD`），在 GitHub Actions 中：

```yaml
- name: Sign and package
  shell: pwsh
  run: |
    [IO.File]::WriteAllBytes("cert.pfx", [Convert]::FromBase64String($env:PFX_BASE64))
    $env:ZSIGN_PFX_PASSWORD = $env:PFX_PASSWORD
    ./packaging/build.ps1 -SkipInstall -Sign -PfxPath cert.pfx
```

SignPath Foundation 则走它提供的 GitHub Action，由平台在 HSM 中完成签名，PFX 不落地。

## 注意事项

- 不要提交 `.pfx` / `.p12` / 证书密码；`.gitignore` 已忽略这些文件。
- 签名会改变 exe 字节，必须重新生成校验值（`build.ps1` 已自动生成 `SHA256SUMS.txt`）。
- 自签名证书只适合自测或内网分发，不要作为对外发布方案。
- 拿到新证书后先用 `verify_exe.py` 跑一遍，确认签名没有破坏 onefile 启动。
