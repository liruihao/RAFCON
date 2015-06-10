from awesome_tool.utils import log
logger = log.get_logger(__name__)

from awesome_tool.mvc.config import global_gui_config
from awesome_tool.mvc.controllers.extended_controller import ExtendedController
from awesome_tool.mvc.statemachine_helper import StateMachineHelper

from awesome_tool.mvc.models.state_machine import StateMachineModel
from awesome_tool.mvc.models import ContainerStateModel, StateModel
from awesome_tool.mvc.models.scoped_variable import ScopedVariableModel

from awesome_tool.mvc.views.graphical_editor_gaphas import GraphicalEditorView
from awesome_tool.mvc.views.gap.state import StateView
from awesome_tool.mvc.views.gap.connection import DataFlowView, TransitionView

from gaphas import Canvas
import gaphas.guide


class GraphicalEditorController(ExtendedController):
    """Controller handling the graphical editor

    :param awesome_tool.mvc.models.state_machine.StateMachineModel model: The state machine model, holding the root
        state and the current selection
    :param awesome_tool.mvc.views.graphical_editor.GraphicalEditorView view: The GTK view having an OpenGL rendering
        element
    """

    def __init__(self, model, view):
        """Constructor
        """
        ExtendedController.__init__(self, model, view)
        assert type(view) == GraphicalEditorView
        assert isinstance(self.model, StateMachineModel)
        # assert isinstance(self.view, GraphicalEditorView)
        # assert isinstance(self.view.editor, GraphicalEditor)
        self.root_state_m = model.root_state

        self.canvas = Canvas()
        self.zoom = 3.

    def register_view(self, view):
        """Called when the View was registered
        """
        assert self.view == view
        self.setup_canvas()
        self.view.setup_canvas(self.canvas, self.zoom)
        self.view.connect('new_state_selection', self._select_new_state)
        self.view.connect('remove_state_from_state_machine', self._remove_state_view)

    def register_adapters(self):
        """Adapters should be registered in this method call
        """
        pass

    def register_actions(self, shortcut_manager):
        """Register callback methods for triggered actions

        :param awesome_tool.mvc.shortcut_manager.ShortcutManager shortcut_manager:
        """
        shortcut_manager.add_callback_for_action("add", self._add_execution_state)

    def _add_execution_state(self, *args):
        from awesome_tool.statemachine.enums import StateType
        from awesome_tool.mvc.models import StateModel, TransitionModel, DataFlowModel
        if self.view.editor.has_focus():  # or singleton.global_focus is self:
            selection = self.model.selection.get_all()
            if len(selection) > 0:
                model = selection[0]

                if isinstance(model, StateModel):
                    StateMachineHelper.add_state(model, StateType.EXECUTION)
                if isinstance(model, TransitionModel) or isinstance(model, DataFlowModel):
                    StateMachineHelper.add_state(model.parent, StateType.EXECUTION)

    def _select_new_state(self, view, state):
        if state and isinstance(state, StateView):
            state_m = state.state_m
            if not self.model.selection.is_selected(state_m):
                self.model.selection.clear()
                self.model.selection.set(state_m)

    @ExtendedController.observe("state_machine", after=True)
    def state_machine_change(self, model, prop_name, info):
        """Called on any change within th state machine

        This method is called, when any state, transition, data flow, etc. within the state machine changes. This
        then typically requires a redraw of the graphical editor, to display these changes immediately.

        :param awesome_tool.mvc.models.state_machine.StateMachineModel model: The state machine model
        :param str prop_name: The property that was changed
        :param dict info: Information about the change
        """
        if 'method_name' in info and info['method_name'] == 'root_state_before_change':
            kwargs = info['kwargs']
            if kwargs['method_name'] == 'transition_change':
                transition_m = kwargs['args'][0]
                transition_change_kwargs = kwargs['kwargs']
                transition_v = self.get_view_for_model(transition_m)
                if (transition_change_kwargs['method_name'] == 'to_state' or
                            transition_change_kwargs['method_name'] == 'to_outcome'):
                    transition_v.remove_connection_from_port(transition_v.to_port)
                    transition_v.reset_to_port()
                elif (transition_change_kwargs['method_name'] == 'modify_origin' or
                              transition_change_kwargs['method_name'] == 'from_outcome'):
                    transition_v.remove_connection_from_port(transition_v.from_port)
                    transition_v.reset_from_port()

        if 'method_name' in info and info['method_name'] == 'root_state_after_change':
            information = info
            parent_state_m = information['kwargs']['model']
            method_name = information['kwargs']['method_name']
            arguments = information['kwargs']['args']
            result = information['kwargs']['result']
            if method_name == 'state_change':
                information = info['kwargs']['info']
                parent_state_m = information['model']
                method_name = information['method_name']
                arguments = information['args']
                result = information['result']

            if method_name == 'add_state':
                new_state = arguments[1]
                new_state_m = parent_state_m.states[new_state.state_id]
                self.add_state_view_to_parent(new_state_m, parent_state_m)
            # ----------------------------------
            #           TRANSITIONS
            # ----------------------------------
            elif method_name == 'add_transition':
                transitions_models = parent_state_m.transitions
                transition_id = result
                for transition_m in transitions_models:
                    if transition_m.transition.transition_id == transition_id:
                        self.add_transition_view_for_model(transition_m, parent_state_m)
            elif method_name == 'remove_transition':
                self.remove_transition_view_from_parent_view(parent_state_m)
            elif method_name == 'transition_change':
                transition_m = arguments[0]
                transition_v = self.get_view_for_model(transition_m)
                self.connect_transition_handle_to_state(transition_v, transition_m, parent_state_m)
            # ----------------------------------
            #           DATA FLOW
            # ----------------------------------
            elif method_name == 'add_data_flow':
                data_flow_models = parent_state_m.data_flows
                data_flow_id = result
                for data_flow_m in data_flow_models:
                    if data_flow_m.data_flow.data_flow_id == data_flow_id:
                        self.add_data_flow_view_for_model(data_flow_m, parent_state_m)
            elif method_name == 'remove_data_flow':
                self.remove_data_flow_view_from_parent_view(parent_state_m)
            elif method_name == 'data_flow_change':
                data_flow_m = arguments[0]
                data_flow_v = self.get_view_for_model(data_flow_m)
                self.connect_data_flow_handle_to_state(data_flow_v, data_flow_m, parent_state_m)
            # ----------------------------------
            #           OUTCOMES
            # ----------------------------------
            elif method_name == 'add_outcome':
                state_m = information['kwargs']['model']
                state_v = self.get_view_for_model(state_m)
                for outcome_m in state_m.outcomes:
                    if outcome_m.outcome.outcome_id == result:
                        state_v.add_outcome(outcome_m)
                        self.canvas.request_update(state_v)
            elif method_name == 'remove_outcome':
                state_m = information['kwargs']['model']
                state_v = self.get_view_for_model(state_m)
                for outcome_v in state_v.outcomes:
                    if outcome_v.outcome_id == arguments[1]:
                        state_v.remove_outcome(outcome_v)
                        self.canvas.request_update(state_v)
            # ----------------------------------
            #           DATA PORTS
            # ----------------------------------
            else:
                print method_name

    @ExtendedController.observe("root_state", assign=True)
    def root_state_change(self, model, prop_name, info):
        """Called when the root state was exchanged

        Exchanges the local reference to the root state and redraws.

        :param awesome_tool.mvc.models.state_machine.StateMachineModel model: The state machine model
        :param str prop_name: The root state
        :param dict info: Information about the change
        """
        if self.root_state_m is not model.root_state:
            logger.debug("The root state was exchanged")
            self.root_state_m = model.root_state


    @ExtendedController.observe("selection", after=True)
    def selection_change(self, model, prop_name, info):
        """Called when the selection was changed externally

        Updates the local selection and redraws.

        :param awesome_tool.mvc.selection.Selection model: The state machine model
        :param str prop_name: The selection
        :param dict info: Information about the change
        """
        pass

    def connect_transition_handle_to_state(self, transition_v, transition_m, parent_state_m):
        parent_state_v = self.get_view_for_model(parent_state_m)

        self.canvas.disconnect_item(transition_v)
        self.draw_transition(transition_m, transition_v, parent_state_m, parent_state_v, False)
        self.canvas.update()

    def connect_data_flow_handle_to_state(self, data_flow_v, data_flow_m, parent_state_m):
        self.canvas.disconnect_item(data_flow_v)
        self.draw_data_flow(data_flow_m, data_flow_v, parent_state_m)
        self.canvas.update()

    @staticmethod
    def get_state_model(container_m, state_id):
        if state_id is None:
            return container_m
        return container_m.states[state_id]

    def add_transition_view_for_model(self, transition_m, parent_state_m):
        parent_state_v = self.get_view_for_model(parent_state_m)

        new_transition_hierarchy_level = parent_state_v.hierarchy_level
        new_transition_v = TransitionView(transition_m, new_transition_hierarchy_level)

        self.canvas.add(new_transition_v, parent_state_v)

        self.draw_transition(transition_m, new_transition_v, parent_state_m, parent_state_v)

    def add_data_flow_view_for_model(self, data_flow_m, parent_state_m):
        parent_state_v = self.get_view_for_model(parent_state_m)

        new_data_flow_hierarchy_level = parent_state_v.hierarchy_level
        new_data_flow_v = DataFlowView(data_flow_m, new_data_flow_hierarchy_level)

        self.canvas.add(new_data_flow_v, parent_state_v)

        self.draw_data_flow(data_flow_m, new_data_flow_v, parent_state_m)

    def _remove_connection_view(self, parent_state_m, transitions=True):
        parent_state_v = self.get_view_for_model(parent_state_m)

        if transitions:
            available_connections = parent_state_m.transitions
        else:
            available_connections = parent_state_m.data_flows

        children = self.canvas.get_children(parent_state_v)
        for child in list(children):
            if transitions and isinstance(child, TransitionView) and child.transition_m not in available_connections:
                child.remove_connection_from_ports()
                self.canvas.remove(child)
            elif not transitions and isinstance(child, DataFlowView) and child.data_flow_m not in available_connections:
                child.remove_connection_from_ports()
                self.canvas.remove(child)

    def remove_data_flow_view_from_parent_view(self, parent_state_m):
        self._remove_connection_view(parent_state_m, False)

    def remove_transition_view_from_parent_view(self, parent_state_m):
        self._remove_connection_view(parent_state_m)

    def get_view_for_model(self, model):
        # TODO: change model name of each Element to "model" to reduce size of method
        for item in self.canvas.get_root_items():
            if isinstance(item, StateView) and item.state_m is model:
                return item
            elif isinstance(item, TransitionView) and item.transition_m is model:
                return item
            elif isinstance(item, DataFlowView) and item.data_flow_m is model:
                return item
            for child in list(self.canvas.get_all_children(item)):
                if isinstance(child, StateView) and child.state_m is model:
                    return child
                elif isinstance(child, TransitionView) and child.transition_m is model:
                    return child
                elif isinstance(child, DataFlowView) and child.data_flow_m is model:
                    return child

    def add_state_view_to_parent(self, state_m, parent_state_m):
        parent_state_v = self.get_view_for_model(parent_state_m)

        new_state_side_size = min(parent_state_v.width * 0.2, parent_state_v.height * 0.2)
        new_state_hierarchy_level = parent_state_v.hierarchy_level + 1

        new_state_v = StateView(state_m, (new_state_side_size, new_state_side_size), new_state_hierarchy_level)

        state_m.temp['gui']['editor']['view'] = new_state_v

        self.canvas.add(new_state_v, parent_state_v)

        for outcome_m in state_m.outcomes:
            new_state_v.add_outcome(outcome_m)

        for input_port_m in state_m.input_data_ports:
            new_state_v.add_input_port(input_port_m)

        for output_port_m in state_m.output_data_ports:
            new_state_v.add_output_port(output_port_m)

    def _remove_state_view(self, view):
        selection = self.model.selection.get_all()
        if len(selection) > 0:
            StateMachineHelper.delete_models(selection)
            self.model.selection.clear()

    def setup_canvas(self):

        self.setup_state(self.root_state_m)

    def setup_state(self, state_m, parent=None, rel_pos=(10, 10), size=(100, 100), hierarchy_level=1):

        """Draws a (container) state with all its content

        Mainly contains the logic for drawing (e. g. reading and calculating values). The actual drawing process is
        done in the view, which is called from this method with the appropriate arguments.

        :param awesome_tool.mvc.models.state.StateModel state_m: The state to be drawn
        :param tuple rel_pos: The default relative position (x, y) if there is no relative position stored
        :param tuple size: The default size (width, height) if there is no size stored
        :param float depth: The hierarchy level of the state
        """
        assert isinstance(state_m, StateModel)
        state_meta = state_m.meta['gui']['editor']
        state_temp = state_m.temp['gui']['editor']

        # Use default values if no size information is stored
        if not isinstance(state_meta['size'], tuple):
            state_meta['size'] = size

        size = state_meta['size']

        if isinstance(state_meta['rel_pos'], tuple):
            rel_pos = state_meta['rel_pos']
            if not isinstance(self.model.meta['gui']['editor']['invert_y'], bool) or \
                    self.model.meta['gui']['editor']['invert_y']:
                rel_pos = (rel_pos[0], -rel_pos[1])

        # # Was the state selected?
        # selected_states = self.model.selection.get_states()
        # selected = False if state_m not in selected_states else True
        #
        # # Is the state active (executing)?
        # active = 0
        # if state_m.state.active:
        #     if self.has_content(state_m) and state_m.state.child_execution:
        #         active = 0.5
        #     else:
        #         active = 1

        state_v = StateView(state_m, size, hierarchy_level)
        self.canvas.add(state_v, parent)
        state_temp['view'] = state_v
        state_v.matrix.translate(*rel_pos)

        for outcome_m in state_m.outcomes:
            state_v.add_outcome(outcome_m)
            # state_v.add_double_port_outcome(outcome_m)

        for input_port_m in state_m.input_data_ports:
            state_v.add_input_port(input_port_m)

        for output_port_m in state_m.output_data_ports:
            state_v.add_output_port(output_port_m)

        if parent is not None:
            # Keep state within parent
            pass

        if isinstance(state_m, ContainerStateModel):
            num_child_state = 0
            state_width = size[0]
            state_height = size[1]

            num_scoped_variables = 0
            for scoped_variable_m in state_m.scoped_variables:
                if not isinstance(scoped_variable_m.meta['gui']['editor']['size'], tuple):
                    port_height = min(state_meta['size']) / 15.
                    port_width = min(state_meta['size']) / 5.
                    scoped_variable_m.meta['gui']['editor']['size'] = (port_width, port_height)
                port_size = scoped_variable_m.meta['gui']['editor']['size']

                if isinstance(scoped_variable_m.meta['gui']['editor']['rel_pos'], tuple):
                    rel_pos = scoped_variable_m.meta['gui']['editor']['rel_pos']
                elif isinstance(scoped_variable_m.meta['gui']['editor']['inner_rel_pos'], tuple):
                    rel_pos = scoped_variable_m.meta['gui']['editor']['inner_rel_pos']
                else:
                    # Put scoped variables by default row-wise in at the top
                    port_height = port_size[1]
                    port_width = port_size[0]
                    max_cols = state_width // port_width
                    (row, col) = divmod(num_scoped_variables, max_cols)
                    rel_pos = (col * port_width, -port_height * (2 * row + 1))
                    scoped_variable_m.meta['gui']['editor']['rel_pos'] = rel_pos

                if not isinstance(self.model.meta['gui']['editor']['invert_y'], bool) or \
                        self.model.meta['gui']['editor']['invert_y']:
                    rel_pos = (rel_pos[0], -rel_pos[1])

                scoped_variable_v = state_v.add_scoped_variable(scoped_variable_m, port_size)
                scoped_variable_v.matrix.translate(*rel_pos)
                num_scoped_variables += 1

            for child_state in state_m.states.itervalues():
                # Calculate default positions for the child states
                # Make the inset from the top left corner

                child_width = state_width / 5.
                child_height = state_height / 5.
                child_size = (child_width, child_height)
                child_spacing = max(child_size) * 1.2

                max_cols = state_width // child_spacing
                (row, col) = divmod(num_child_state, max_cols)
                child_rel_pos_x = col * child_spacing + child_spacing - child_width
                child_rel_pos_y = child_spacing * (1.5 * row + 1)
                child_rel_pos = (child_rel_pos_x, child_rel_pos_y)
                num_child_state += 1

                self.setup_state(child_state, state_v, child_rel_pos, child_size, hierarchy_level + 1)

            # if global_gui_config.get_config_value('show_data_flows', True):
            #     self.draw_inner_data_ports(state_m, depth)
            #
            self.draw_transitions(state_m, hierarchy_level)

            if global_gui_config.get_config_value('show_data_flows', True):
                self.draw_data_flows(state_m, hierarchy_level)

                # self._handle_new_transition(state_m, depth)
                #
                # if global_gui_config.get_config_value('show_data_flows', True):
                #     self._handle_new_data_flow(state_m, depth)

    def draw_transitions(self, parent_state_m, hierarchy_level):
        """Draws the transitions belonging to a state

        The method takes all transitions from the given state and calculates their start and end point positions.
        Those are passed together with the waypoints to the view of the graphical editor.

        :param awesome_tool.mvc.models.container_state.ContainerStateModel parent_state_m: The model of the container
            state, of which the transitions shall be drawn
        """
        parent_state_v = parent_state_m.temp['gui']['editor']['view']
        assert isinstance(parent_state_v, StateView)
        for transition_m in parent_state_m.transitions:

            transition_v = TransitionView(transition_m, hierarchy_level)
            self.canvas.add(transition_v, parent_state_v)

            self.draw_transition(transition_m, transition_v, parent_state_m, parent_state_v)

    def draw_transition(self, transition_m, transition_v, parent_state_m, parent_state_v, use_waypoints=True):
        try:
            # Get id and references to the from and to state
            from_state_id = transition_m.transition.from_state
            if from_state_id is None:
                parent_state_v.connect_to_income(transition_v, transition_v.from_handle())
            else:
                from_state_m = parent_state_m.states[from_state_id]
                from_state_v = from_state_m.temp['gui']['editor']['view']
                from_outcome_id = transition_m.transition.from_outcome
                from_state_v.connect_to_outcome(from_outcome_id, transition_v, transition_v.from_handle())
                # from_state_v.connect_to_double_port_outcome(from_outcome_id, transition_v, transition_v.from_handle(), False)

            to_state_id = transition_m.transition.to_state
            to_state_m = None if to_state_id is None else parent_state_m.states[to_state_id]

            if to_state_m is None:  # Transition goes back to parent
                # Set the to coordinates to the outcome coordinates received earlier
                to_outcome_id = transition_m.transition.to_outcome
                parent_state_v.connect_to_outcome(to_outcome_id, transition_v, transition_v.to_handle())
                # parent_state_v.connect_to_double_port_outcome(to_outcome_id, transition_v, transition_v.to_handle(), True)
            else:
                # Set the to coordinates to the center of the next state
                to_state_v = to_state_m.temp['gui']['editor']['view']
                to_state_v.connect_to_income(transition_v, transition_v.to_handle())

            if use_waypoints:
                for waypoint in transition_m.meta['gui']['editor']['waypoints']:
                    if not isinstance(self.model.meta['gui']['editor']['invert_y'], bool) or \
                            self.model.meta['gui']['editor']['invert_y']:
                        waypoint = (waypoint[0], -waypoint[1])
                    transition_v.add_waypoint(waypoint)

            # Let the view draw the transition and store the returned OpenGL object id
            # if transition_m in self.model.selection.get_transitions():
            #     transition_v.selected = True
            # line_width = self.view.editor.transition_stroke_width(parent_state_m)

        except AttributeError as e:
            logger.error("Cannot connect transition: {0}".format(e))
            try:
                self.canvas.remove(transition_v)
            except KeyError:
                pass

    def draw_data_flows(self, parent_state_m, hierarchy_level):
        """Draw all data flows contained in the given container state

        The method takes all data flows from the given state and calculates their start and end point positions.
        Those are passed together with the waypoints to the view of the graphical editor.

        :param awesome_tool.mvc.models.container_state.ContainerStateModel parent_state_m: The model of the container
            state, of which the data flows shall be drawn
        """
        parent_state_v = parent_state_m.temp['gui']['editor']['view']
        assert isinstance(parent_state_v, StateView)
        for data_flow_m in parent_state_m.data_flows:

            data_flow_v = DataFlowView(data_flow_m, hierarchy_level)
            self.canvas.add(data_flow_v, parent_state_v)

            self.draw_data_flow(data_flow_m, data_flow_v, parent_state_m)

    @staticmethod
    def draw_data_flow(data_flow_m, data_flow_v, parent_state_m):
        # Get id and references to the from and to state
        from_state_id = data_flow_m.data_flow.from_state
        from_state_m = parent_state_m if from_state_id == parent_state_m.state.state_id else parent_state_m.states[
            from_state_id]
        from_state_v = from_state_m.temp['gui']['editor']['view']

        to_state_id = data_flow_m.data_flow.to_state
        to_state_m = parent_state_m if to_state_id == parent_state_m.state.state_id else parent_state_m.states[
            to_state_id]
        to_state_v = to_state_m.temp['gui']['editor']['view']

        from_key = data_flow_m.data_flow.from_key
        to_key = data_flow_m.data_flow.to_key

        from_port_m = StateMachineHelper.get_data_port_model(from_state_m, from_key)
        to_port_m = StateMachineHelper.get_data_port_model(to_state_m, to_key)

        if from_port_m is None:
            logger.warn('Cannot find model of the from data port {0}, ({1})'.format(from_key,
                                                                                    data_flow_m.data_flow))
            return
        if to_port_m is None:
            logger.warn('Cannot find model of the to data port {0}, ({1})'.format(to_key, data_flow_m.data_flow))
            return

        # For scoped variables, there is no inner and outer connector
        if isinstance(from_port_m, ScopedVariableModel):
            from_state_v.connect_to_scoped_variable_output(from_key, data_flow_v, data_flow_v.from_handle())
        elif from_port_m in from_state_m.input_data_ports:
            from_state_v.connect_to_input_port(from_key, data_flow_v, data_flow_v.from_handle())
        elif from_port_m in from_state_m.output_data_ports:
            from_state_v.connect_to_output_port(from_key, data_flow_v, data_flow_v.from_handle())

        if isinstance(to_port_m, ScopedVariableModel):
            to_state_v.connect_to_scoped_variable_input(to_key, data_flow_v, data_flow_v.to_handle())
        elif to_port_m in to_state_m.output_data_ports:
            to_state_v.connect_to_output_port(to_key, data_flow_v, data_flow_v.to_handle())
        elif to_port_m in to_state_m.input_data_ports:
            to_state_v.connect_to_input_port(to_key, data_flow_v, data_flow_v.to_handle())
