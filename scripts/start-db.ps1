# Helper script to ensure Docker is in PATH and start PostgreSQL container
$dockerBin = "C:\Users\koay\AppData\Local\Programs\DockerDesktop\resources\bin"
if (Test-Path $dockerBin) {
    if ($env:Path -notlike "*$dockerBin*") {
        $env:Path = "$dockerBin;$env:Path"
    }
}
docker compose up -d postgres
