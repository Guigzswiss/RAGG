param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

Add-Type -AssemblyName System.Drawing

$image = [System.Drawing.Image]::FromFile($Path)
try {
    # Les photos/scans stockent souvent la rotation dans une metadonnee EXIF (tag
    # 0x0112) plutot que dans les pixels eux-memes. On l'applique reellement a
    # l'image pour que la largeur/hauteur ci-dessous refletent l'orientation vraie.
    $exifOrientationTag = 0x0112
    if ($image.PropertyIdList -contains $exifOrientationTag) {
        $orientation = [BitConverter]::ToUInt16($image.GetPropertyItem($exifOrientationTag).Value, 0)
        switch ($orientation) {
            2 { $image.RotateFlip([System.Drawing.RotateFlipType]::RotateNoneFlipX) }
            3 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipNone) }
            4 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipX) }
            5 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipX) }
            6 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone) }
            7 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate270FlipX) }
            8 { $image.RotateFlip([System.Drawing.RotateFlipType]::Rotate270FlipNone) }
        }
    }

    $printDocument = New-Object System.Drawing.Printing.PrintDocument
    $printDocument.DefaultPageSettings.Landscape = ($image.Width -gt $image.Height)
    $printDocument.add_PrintPage({
        param($sender, $e)
        $bounds = $e.MarginBounds
        $ratio = [Math]::Min($bounds.Width / $image.Width, $bounds.Height / $image.Height)
        $width = $image.Width * $ratio
        $height = $image.Height * $ratio
        $x = $bounds.X + (($bounds.Width - $width) / 2)
        $y = $bounds.Y + (($bounds.Height - $height) / 2)
        $e.Graphics.DrawImage($image, $x, $y, $width, $height)
    })
    $printDocument.Print()
}
finally {
    $image.Dispose()
}
