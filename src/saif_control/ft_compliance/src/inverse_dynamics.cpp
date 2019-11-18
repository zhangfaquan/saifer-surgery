#include <ros/ros.h>
#include <geometry_msgs/WrenchStamped.h>
#include <sensor_msgs/JointState.h>
#include <trajectory_msgs/JointTrajectory.h>
#include <trajectory_msgs/JointTrajectoryPoint.h>
#include <moveit/move_group_interface/move_group_interface.h>
#include <moveit/robot_model_loader/robot_model_loader.h>
#include <moveit/robot_model/robot_model.h>
#include <moveit/robot_state/robot_state.h>

#define FTHRESH 40

class IDyn {
	public:
		IDyn();
		~IDyn();
	private:
		std::string group_name;
		ros::NodeHandle n;
//		moveit::planning_interface::MoveGroupInterface *mg;			
		robot_model_loader::RobotModelLoader rl;
		robot_model::RobotModelPtr kinematic_model;
		robot_state::RobotStatePtr kinematic_state;

		Eigen::MatrixXd Jinv;
		Eigen::MatrixXd Fbase;
		bool jac;
		bool ft_meas;

		ros::Subscriber sub1;
		ros::Subscriber sub2;
		void ft_callback(const geometry_msgs::WrenchStamped& msg);
		void jt_callback(const sensor_msgs::JointState& msg);
		void ft_ready(Eigen::MatrixXd ft);
		void ft_push(Eigen::MatrixXd ft, const geometry_msgs::WrenchStamped& msg);
		void ft_filter(Eigen::MatrixXd ft);
		std::vector<std::string> joint_names;
		std::vector<double> joint_angles;
		ros::Publisher pub;

		int state;
		int counter;
		
};

IDyn::IDyn(void)
{
	sub1 = n.subscribe("/red/robotiq_ft_wrench_compensated",1,&IDyn::ft_callback,this);	
	sub2 = n.subscribe("/joint_states",1,&IDyn::jt_callback,this);	
	
	pub = n.advertise<trajectory_msgs::JointTrajectory>("/red/vel_test",1);
	group_name = "red_arm";

	jac = false;
	ft_meas = false;

	rl = robot_model_loader::RobotModelLoader("robot_description");
	kinematic_model = rl.getModel();
	ros::spin();
}

IDyn::~IDyn(void)
{
//	delete mg;
}

void IDyn::ft_callback(const geometry_msgs::WrenchStamped& msg)
{
	if (jac)
	{
		ROS_INFO("STATE: %d",state);
		Eigen::MatrixXd ft(6,1);
		ft << msg.wrench.force.y, -msg.wrench.force.x, msg.wrench.force.z, msg.wrench.torque.y,-msg.wrench.torque.x,msg.wrench.torque.z;
		if ((ft).squaredNorm() > FTHRESH)
		{

			Eigen::MatrixXd K = Eigen::MatrixXd::Zero(6,6);
			for (int i = 0; i < 6; i++)
			{
				if (i < 3)
				{
					K(i,i) = 0.01;
				}
				else
				{
					K(i,i) = 0.0;
				}
			}
	

			Eigen::MatrixXd twist = K*(-ft);
			Eigen::MatrixXd joint_vel = Jinv*twist; 

			trajectory_msgs::JointTrajectory jt;
			jt.header = msg.header;
			jt.joint_names =  joint_names;
			trajectory_msgs::JointTrajectoryPoint point;
			point.time_from_start = ros::Duration(1.0);
			point.positions = joint_angles;
	
			for (int i = 0; i < int(joint_vel.rows()); i++)
			{
				point.positions[i] = point.positions[i] + 0.1*joint_vel(i,0);
				point.velocities.push_back(joint_vel(i,0));
			}
			jt.points.push_back(point);	
			for (int i = 0; i < int(joint_vel.rows()); i++)
			{
				point.velocities[i] = 0.0;
			}
			point.time_from_start = ros::Duration(2.0);	
			jt.points.push_back(point);	
			pub.publish(jt);	
		}
	}
}

void IDyn::jt_callback(const sensor_msgs::JointState& msg)
{
//	ROS_INFO("Got joint message");
	robot_state::RobotStatePtr kinematic_state(new robot_state::RobotState(kinematic_model));
	kinematic_state->setToDefaultValues();
	const robot_state::JointModelGroup* joint_model_group = kinematic_model->getJointModelGroup(group_name);

	joint_names = joint_model_group->getVariableNames();
//	std::vector<double> joint_values;
//	joint_angles = msg.position;
	
	kinematic_state->setVariableValues(msg);
	kinematic_state->copyJointGroupPositions(joint_model_group, joint_angles);	
		
//	for (std::size_t i = 0; i < joint_names.size(); ++i)
//	{
//		ROS_INFO("Joint %s: %f", joint_names[i].c_str(), joint_values[i]);
//		ROS_INFO("Joint %s: %f", msg.name[i].c_str(), msg.position[i]);
//	}

	Eigen::Vector3d reference_point_position(0.0, 0.0, 0.0);
	Eigen::MatrixXd jacobian;

	kinematic_state->getJacobian(joint_model_group, kinematic_state->getLinkModel(joint_model_group->getLinkModelNames().back()), reference_point_position, jacobian);	
	
	Jinv = jacobian.completeOrthogonalDecomposition().pseudoInverse();
//	ROS_INFO_STREAM("Jacobian: \n" << jacobian << "\n" << "PseudoInverse" << "\n" << Jinv << "\n");
	jac = true;
	return;
}


int main(int argc, char **argv)
{
	ros::init(argc, argv, "inverse_dynamics");

	IDyn inverse_dynamics;

//	const robot_state::JointModelGroup* joint_model_group = move_group.getCurrentState()->getJointModelGroup(PLANNING_GROUP);
	return 0;
}
