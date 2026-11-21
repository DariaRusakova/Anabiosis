#include "ElementalFirstPersonAnimInstance.h"
#include "ElementalFirstPersonCharacter.h"
#include "ElementalWeaponComponent.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "AnimNodes/AnimNode_CopyPoseFromMesh.h"
#include "AnimNodes/AnimNode_LayeredBoneBlend.h"
#include "AnimNodes/AnimNode_SequenceEvaluator.h"
#include "AnimNodes/AnimNode_Slot.h"
#include "BoneControllers/AnimNode_TwoBoneIK.h"
#include "BoneControllers/AnimNode_ModifyBone.h"
#include "Components/SkeletalMeshComponent.h"

namespace
{
struct FElementalAnimProxy final : FAnimInstanceProxy
{
    FAnimNode_CopyPoseFromMesh CopyBody;
    FAnimNode_SequenceEvaluator_Standalone Hold;
    FAnimNode_Slot Attack;
    FAnimNode_LayeredBoneBlend Arms;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_TwoBoneIK RightIK, LeftIK;
    FAnimNode_ModifyBone RightWrist, LeftWrist;
    FAnimNode_ConvertComponentToLocalSpace Root;

    explicit FElementalAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance)
    {
        CopyBody.bUseAttachedParent = true;
        CopyBody.bCopyCurves = true;
        Hold.SetTeleportToExplicitTime(true);
        Hold.SetExplicitTime(0);
        Attack.Source.SetLinkNode(&Hold);
        Attack.SlotName = TEXT("DefaultSlot");
        Attack.bAlwaysUpdateSourcePose = true;
        Arms.BasePose.SetLinkNode(&CopyBody);
        Arms.AddPose();
        Arms.BlendPoses[0].SetLinkNode(&Attack);
        Arms.BlendWeights[0] = 1;
        Arms.bMeshSpaceRotationBlend = true;
        for (const FName Bone : {FName(TEXT("clavicle_r")), FName(TEXT("clavicle_l"))})
        {
            FBranchFilter Filter;
            Filter.BoneName = Bone;
            Filter.BlendDepth = 1;
            Arms.LayerSetup[0].BranchFilters.Add(Filter);
        }
        ToComponent.LocalPose.SetLinkNode(&Arms);
        RightIK.ComponentPose.SetLinkNode(&ToComponent);
        LeftIK.ComponentPose.SetLinkNode(&RightIK);
        RightIK.IKBone.BoneName = TEXT("hand_r");
        LeftIK.IKBone.BoneName = TEXT("hand_l");
        for (FAnimNode_TwoBoneIK* IK : {&RightIK, &LeftIK})
        {
            IK->EffectorLocationSpace = BCS_ComponentSpace;
            IK->JointTargetLocationSpace = BCS_ComponentSpace;
            // Preserve the hold pose's component-space wrist orientation;
            // the final wrist nodes add the view/weapon rotation once.
            IK->bMaintainEffectorRelRot = false;
            IK->bTakeRotationFromEffectorSpace = false;
            IK->bAllowStretching = false;
        }
        RightWrist.ComponentPose.SetLinkNode(&LeftIK);
        LeftWrist.ComponentPose.SetLinkNode(&RightWrist);
        RightWrist.BoneToModify.BoneName = TEXT("hand_r");
        LeftWrist.BoneToModify.BoneName = TEXT("hand_l");
        for (FAnimNode_ModifyBone* Wrist : {&RightWrist, &LeftWrist})
        {
            Wrist->RotationMode = BMM_Additive;
            Wrist->RotationSpace = BCS_ComponentSpace;
        }
        Root.ComponentPose.SetLinkNode(&LeftWrist);
    }

    virtual FAnimNode_Base* GetCustomRootNode() override { return &Root; }
    virtual void GetCustomNodes(TArray<FAnimNode_Base*>& Out) override
    {
        Out.Append({&CopyBody, &Hold, &Attack, &Arms, &ToComponent,
                    &RightIK, &LeftIK, &RightWrist, &LeftWrist, &Root});
    }
    virtual void PreUpdate(UAnimInstance* Instance, float Dt) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, Dt);
        const AElementalFirstPersonCharacter* Owner = Cast<AElementalFirstPersonCharacter>(Instance->GetOwningActor());
        if (!Owner || !Owner->ElementalWeapons) return;
        CopyBody.SourceMeshComponent = Owner->GetMesh();
        const FElementalArmTargets Targets = Owner->ElementalWeapons->GetArmTargets();
        // All UObject access happens here on the game thread, before worker evaluation.
        Hold.SetSequence(Targets.Pose);
        Arms.BlendWeights[0] = Targets.Valid ? 1.f : 0.f;
        RightIK.Alpha = LeftIK.Alpha = RightWrist.Alpha = LeftWrist.Alpha = Targets.Valid ? 1.f : 0.f;
        RightIK.EffectorLocation = Targets.RightHand;
        LeftIK.EffectorLocation = Targets.LeftHand;
        RightIK.JointTargetLocation = Targets.RightElbow;
        LeftIK.JointTargetLocation = Targets.LeftElbow;
        RightWrist.Rotation = LeftWrist.Rotation = Targets.WristRotation;
    }
};
}

FAnimInstanceProxy* UElementalFirstPersonAnimInstance::CreateAnimInstanceProxy()
{
    return new FElementalAnimProxy(this);
}
void UElementalFirstPersonAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
    delete static_cast<FElementalAnimProxy*>(InProxy);
}
