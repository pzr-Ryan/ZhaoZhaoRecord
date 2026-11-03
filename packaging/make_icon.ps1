param(
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $Output) { $Output = Join-Path $root "assets\icon.ico" }
$outDir = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Add-Type -AssemblyName System.Drawing

$canvasSize = 256
$bitmap = New-Object System.Drawing.Bitmap($canvasSize, $canvasSize, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$graphics.Clear([System.Drawing.Color]::Transparent)

$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$radius = 54
$margin = 8
$size = $canvasSize - 2 * $margin
$diameter = 2 * $radius
$path.AddArc($margin, $margin, $diameter, $diameter, 180, 90)
$path.AddArc($margin + $size - $diameter, $margin, $diameter, $diameter, 270, 90)
$path.AddArc($margin + $size - $diameter, $margin + $size - $diameter, $diameter, $diameter, 0, 90)
$path.AddArc($margin, $margin + $size - $diameter, $diameter, $diameter, 90, 90)
$path.CloseFigure()

$brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(37, 99, 235))
$graphics.FillPath($brush, $path)

$font = [System.Drawing.Font]::new("Microsoft YaHei UI", 148, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$format = [System.Drawing.StringFormat]::new()
$format.Alignment = [System.Drawing.StringAlignment]::Center
$format.LineAlignment = [System.Drawing.StringAlignment]::Center
$rect = [System.Drawing.RectangleF]::new(0, -8, [float]$canvasSize, [float]$canvasSize)
$graphics.DrawString([string][char]0x00A5, $font, [System.Drawing.Brushes]::White, $rect, $format)

$sizes = @(256, 128, 64, 48, 32, 16)
$pngs = @()
foreach ($dim in $sizes) {
    if ($dim -eq $canvasSize) {
        $frame = $bitmap
    } else {
        $frame = New-Object System.Drawing.Bitmap($dim, $dim, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $g2 = [System.Drawing.Graphics]::FromImage($frame)
        $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g2.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g2.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $g2.Clear([System.Drawing.Color]::Transparent)
        $g2.DrawImage($bitmap, 0, 0, $dim, $dim)
        $g2.Dispose()
    }
    $stream = New-Object System.IO.MemoryStream
    $frame.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngs += ,$stream.ToArray()
    if ($dim -ne $canvasSize) { $frame.Dispose() }
    $stream.Dispose()
}

$file = [System.IO.File]::Create($Output)
$writer = New-Object System.IO.BinaryWriter($file)
$writer.Write([UInt16]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $dim = $sizes[$i]
    $writer.Write([byte]$(if ($dim -ge 256) { 0 } else { $dim }))
    $writer.Write([byte]$(if ($dim -ge 256) { 0 } else { $dim }))
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]32)
    $writer.Write([UInt32]$pngs[$i].Length)
    $writer.Write([UInt32]$offset)
    $offset += $pngs[$i].Length
}
foreach ($png in $pngs) { $writer.Write($png) }
$writer.Flush()
$writer.Close()
$file.Close()
$graphics.Dispose()
$bitmap.Dispose()
$brush.Dispose()
$font.Dispose()
$path.Dispose()

Write-Output ("icon written: " + $Output + " (" + (Get-Item $Output).Length + " bytes)")
