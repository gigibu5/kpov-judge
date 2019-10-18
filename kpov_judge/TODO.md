# Web

* Popravi omrežja na graphviz grafih.
* Navodila za qemu
    * qemu-system-x86_64 -enable-kvm -serial mon:stdio -nographic -m 1G -netdev bridge,br=virbr0,id=n2 -device e1000,netdev=n2 kpov.qcow2
    Se da optimizirati / poenostaviti switche za omrežne vmesnike?

# Security

* Zahtevaj avtentikacijo (basic auth) za prenos slik diskov.

# Tasks

* Navodila iz taskdir/task.py prestaviti v taskdir/instructions/{en,si,…}.html.
    * Popravi, da add_task prebere navodila z diska (če obstajajo, sicer fallback na task.py).
* Proper lokalizacija test_task.py.
