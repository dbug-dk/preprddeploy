#! coding=utf8
# Filename    : htmltemplate.py
# Description : 
# Author      : dengken
# History:
#    1.  , dengken, first create

sorted_module_html = '''<div class="panel-group" id="{{ method }}Process" role="tablist" aria-multiselectable="true">
                       {% for module in sorted_module_list %}
                       <div class="panel panel-default" id='{{ module }}-process-panel'>
                           <div class="panel-heading" role="tab">
                               <h4 class="panel-title">
                                   <a role="button" data-toggle="collapse" data-parent="#{{ method }}Process"
                                      href="#collapse-{{ module }}" aria-expanded="false"
                                      aria-controls="collapse-{{ module }}" class="collapsed">
                                   #{{ forloop.counter }} - {{ module }}
                                   </a>
                               </h4>
                           </div>
                           <div id="collapse-{{ module }}" class="panel-collapse collapse" role="tabpanel"
                                aria-labelledby="{{ module }}">
                                <div class="panel-body" id="{{module}}-info-body">
                                </div>
                           </div>
                       </div>
                       {% endfor %}
                   </div>'''

ami_target_html = u'''<div>业务AMI制作目标实例列表获取完成。<br/>实例信息：</div>
                      <table class="table table-striped table-hover">
                          <thead>
                              <tr>
                                  <th>#</th>
                                  <th>模块名</th>
                                  <th>实例ID</th>
                                  <th>实例IP</th>
                                  <th>密钥对</th>
                              </tr>
                          </thead>
                          <tbody>
                              {% for instance_info in dest_instance_info %}
                              <tr>
                                  <td>{{loop.index}}</td>
                                  <td>{{instance_info.3}}</td>
                                  <td>{{instance_info.0}}</td>
                                  <td>{{instance_info.1}}</td>
                                  <td>{{instance_info.2}}</td>
                              </tr>
                              {% endfor %}
                          </tbody>
                      </table>'''

check_result_panel_html = '''<div class="panel panel-{{pass_or_not}}">
                                <div class="panel-heading" role="tab">
                                    <h4 class="panel-title">
                                        <a role="button" data-toggle="collapse" data-parent="#checkResult"
                                           href="#collapse-{{instance_id}}" aria-expanded="false"
                                           class="collapsed">
                                            {{header}}
                                        </a>
                                    </h4>
                                </div>
                                <div id="collapse-{{instance_id}}" class="panel-collapse collapse"
                                     role="tabpanel" aria-labelledby="{{module}}">
                                    <div class="panel-body">
                                        {{result_table}}
                                    </div>
                                </div>
                            </div>'''


create_ami_result_html = u'''<table class="table table-striped table-hover">
                                 <thead>
                                     <tr>
                                         <th>#</th>
                                         <th>模块名</th>
                                         <th>镜像名</th>
                                         <th>镜像ID</th>
                                     </tr>
                                 </thead>
                                 <tbody>
                                     {% for ami in ami_infos %}
                                     <tr>
                                         <td>{{forloop.index}}</td>
                                         <td>{{ami.0}}</td>
                                         <td>{{ami.1}}</td>
                                         <td>{{ami.2}}</td>
                                     </tr>
                                     {% endfor %}
                                 </tbody>
                             </table>'''