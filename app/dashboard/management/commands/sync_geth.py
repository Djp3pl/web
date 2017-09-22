from django.core.management.base import BaseCommand
from django.conf import settings
from economy.eth import getWeb3, getBountyContract
from django.utils import timezone
from dashboard.helpers import syncBountywithWeb3, process_bounty_changes, normalizeURL
from dashboard.models import BountySyncRequest
import time


class Command(BaseCommand):

    help = 'syncs bounties with geth'

    def handle(self, *args, **options):

        # setup

        urls_to_check = BountySyncRequest.objects.filter(processed=False, created_on__gt=(timezone.now() - timezone.timedelta(hours=2))).values_list('github_url',flat=True)

        print("****************************************")
        print("connecting....")
        print("****************************************")

        start_time = int(timezone.now().strftime("%S"))
        web3 = getWeb3(settings.DEFAULT_PROVIDER)
        end_time = int(timezone.now().strftime("%S"))
        connect_time = end_time - start_time

        print("****************************************")
        print("connected to {} (took {} s)".format(web3.currentProvider.__class__, connect_time))
        print("****************************************")

        # get past event topics
        urls = []

        def new_transaction_callback(transaction_hash):
            block = web3.eth.getBlock('latest')
            fromBlock = block['number'] - 1
            _filter = web3.eth.filter({
                "fromBlock": fromBlock,
                "toBlock": "latest",
                "address": settings.BOUNTY_CONTRACT_ADDRESS,
            })

            log_entries = _filter.get(False)
            print('got {} log entrires from web3'.format(len(log_entries)))

            for entry in log_entries:
                result = web3.toAscii(entry['data']);
                result = result[result.find('http'):]
                url = result[:result.find('\x00')]
                url = normalizeURL(url)
                urls.append(url)

            print('got {} url entrires from web3'.format(len(urls)))

            bountyContract = getBountyContract(web3)
            for url in set(urls):
                didChange, old_bounty, new_bounty = syncBountywithWeb3(bountyContract, url)
                print("{} changed, {}".format(didChange, url))
                if didChange: 
                    print("- processing changes");
                    process_bounty_changes(old_bounty, new_bounty)


        web3.eth.filter('pending').watch(new_transaction_callback)
        print('sleeping')
        while True:
            time.sleep(1)

