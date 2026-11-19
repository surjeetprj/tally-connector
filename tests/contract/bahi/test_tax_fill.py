import httpx
import pytest
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.domain.experiments import UncertainWrite,WriteRejected


@pytest.mark.parametrize('case',['success','permission','timeout','malformed'])
def test_known_account_tax_fill_is_narrow_and_never_retries(case):
    row=dict(account_id=283,account_name='Synthetic supplier',party_type='SUPPLIER',is_active=True,
        gstin=None,pan=None,gst_reg_type='Regular')
    if case=='conflict': row['pan']='OTHER1234A'
    writes=[];attempts=[]
    def handler(request):
        if request.method=='GET':
            data={'biz_id':52,'biz_name':'Synthetic business'} if request.url.path.endswith('check_api_biz_setup.php') else row
            return httpx.Response(200,json={'success':True,'data':data})
        assert request.method=='PATCH' and request.url.params['id']=='283'
        import json
        assert json.loads(request.content)=={'gstin':'09CNXPP6229G1Z7','pan':'CNXPP6229G'}
        writes.append(request)
        if case=='timeout': raise httpx.ReadTimeout('Lost acknowledgement')
        if case=='permission': return httpx.Response(403,json={'success':False})
        if case=='malformed': return httpx.Response(200,content=b'not json')
        return httpx.Response(200,json={'success':True,'data':{'account_id':283}})
    client=Client(lambda:'synthetic-key',httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        args=('283',row,{'gstin':'09CNXPP6229G1Z7','pan':'CNXPP6229G'},lambda _:attempts.append(True))
        if case=='success': assert client.update_party(*args).identity=='283'
        else:
            error=WriteRejected if case=='permission' else UncertainWrite if case in {'timeout','malformed'} else ValueError
            with pytest.raises(error):client.update_party(*args)
        assert len(writes)==len(attempts)==(0 if case=='conflict' else 1)
        with pytest.raises(ValueError):client.update_party('283',row,{'account_name':'rename'},lambda _:pytest.fail('No attempt'))
    finally:client.close()
