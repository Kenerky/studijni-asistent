# Studijní Asistent s AI

Tento projekt implementuje lokální AI asistentku (FastAPI + Ollama) nasazenou v Dockeru, běžící v izolované síti s vlastním DHCP a DNS serverem.

## 1. Síťová konfigurace (Host)
Server má nastavenou statickou IP adresu pro izolovaný segment sítě (např. VirtualBox Host-Only nebo Internal Network).

* **IP adresa:** `10.10.10.1`
* **Maska sítě:** `/24` (255.255.255.0)
* **Rozhraní:** *enp0s8* (nebo dle reálného rozhraní)

## 2. Služby sítě (isc-dhcp-server, bind9)
Server zajišťuje DHCP a DNS pro klienty v izolované síti. Konfigurace pro DHCP je v `/etc/dhcp/dhcpd.conf` a `/etc/netplan/00-installer-config.yaml`.
Konfigurace pro DNS `/etc/bind/named.conf.local` + vytvoření zóny `/etc/bind/db.skola.testsudo`

### DHCP Server
* **Rozsah (Scope):** `10.10.10.100` – `10.10.10.200`
* **Option 6 (DNS):** `10.10.10.1` (Tento server)
* **Option 3 (Gateway):** *Nenastaveno* (Plně izolovaná síť bez přístupu k internetu)

### DNS Server
* **Doména (Zóna):** `zamekkurim.test`
* **A-záznam:** `renespanek.zamekkurim.test` ➔ `10.10.10.1`

## 3. Firewall a Porty
Aplikace naslouchá na portu **8081**. Firewall (UFW) povoluje pouze tento port pro aplikaci a nezbytné porty pro infrastrukturu.

**Příkazy pro nastavení:**

sudo ufw allow 8081/tcp
sudo ufw enable

# 4. Spuštění a sestavení kontejnerů na pozadí
docker compose up -d --build

# 5. Stažení AI modelu (nutné provést pouze jednou)
docker exec -it ollama ollama pull gemma3
