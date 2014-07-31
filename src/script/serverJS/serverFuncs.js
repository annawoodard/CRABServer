angular.module("CRABMonitor").
        factory("ServerFuncs", ["ServerData", "ServerUrls", "$http", function(ServerData, ServerUrls, $http) {
                //load basic quota
                var quota = function() {
                    $http(ServerUrls.quotaUrl).then(function(response) {
                        ServerData.basicQuota = response.data.result[0].quota_user_limit*1000;
                        console.log(ServerData.basicQuota);
                    }, function(response) {
                        console.log("Request for basic quota failed with status: " + response.status);
                    });
                };
                //LOAD ALL USERS
                var users = function() {
                    $http(ServerUrls.allUsersUrl).then(function(response) {
                        for (var i = 0; i < response.data.result.length; i++) {
                            ServerData.users.push(response.data.result[i][0]);
                        }
                    }, function(response) {
                        console.log("Request for users  failed with status: " + response.status);
                    });
                };
                //load workflow summary
                var workflows = function(){
					$http(ServerUrls.workflowsUrl).then(function(response){
						if(response.data.result.length > 0){
							for(var i = 0; i < response.data.result.length; i++){
								if(ServerData.workflows[response.data.result[i][0]]){
									ServerData.workflows[response.data.result[i][0]][response.data.result[i][1]] = response.data.result[i][2];
								}else{
									ServerData.workflows[response.data.result[i][0]] = {};
									ServerData.workflows[response.data.result[i][0]][response.data.result[i][1]] = response.data.result[i][2];
								}
							}
						}	
						console.log(ServerData.workflows);
					},function(response){
						console.log("Request for workflows failed with status: "+response.status);
					});
				};

                return {getUsers: users, getQuota: quota, getWorkflows: workflows};
            }]);
