<# Prints this computer's IPv4 addresses. Put the Wi-Fi one in esp32\KHorizon_Headband\secrets.h as BACKEND_HOST. #>
Write-Host "IPv4 addresses on this computer:" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
  ForEach-Object { "{0,-18} {1}" -f $_.IPAddress, $_.InterfaceAlias }
Write-Host "Use the address of your Wi-Fi adapter (usually 192.168.x.x or 10.x.x.x). The ESP32 and this PC must be on the same network."
