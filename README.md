# trustfull-demonstrator

Code for the demonstrator of the Trustfull project

## Instructions

1. Start `vmn*` servers in Azure
2. Install requirements for scripts: `pip install -r scripts/requirements.txt`
3. Initialize Azure container: `docker run -it mcr.microsoft.com/azure-cli` and then run `az login`.
4. Update container name (`CONTAINER`) in [scripts/azure-ssh.py](scripts/azure-ssh.py) if needed
5. Run `scripts/azure-ssh.py`
6. When prompted for ciphertexts:
   1. <https://vmn-webapp.azurewebsites.net/> must be initialized with the new public key:
      Run `curl -i -X POST -F publicKey=@./publicKey 'https://vmn-webapp.azurewebsites.net/publicKey'`.
   2. After voting is done, recover the ciphertexts file from the webapp interface:
      Run `curl 'https://vmn-webapp.azurewebsites.net/ciphertexts' --output ciphertexts`.
   3. Press "Enter" to continue
7. Run `scripts/vbt_tally.py`, results are uploaded and accessible in <https://vmn-webapp.azurewebsites.net/results>
