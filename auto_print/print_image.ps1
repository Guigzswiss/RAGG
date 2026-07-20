param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

Add-Type -AssemblyName System.Drawing

$image = [System.Drawing.Image]::FromFile($Path)
try {
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
